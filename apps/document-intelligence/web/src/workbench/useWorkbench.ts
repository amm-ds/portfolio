import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ApiError, api } from "../api/client";
import type { ExportFormat } from "../api/client";
import type {
  AnalysisResponse,
  DocumentRecord,
  Evidence,
  PageAnalysis,
  PageChatMessage,
} from "../api/types";
import { downloadBlob, downloadStem } from "./download";

export interface SelectedCitation {
  label: string;
  evidence: Evidence;
}

/** In-memory per-page conversation; citations decorate assistant turns but are never resent. */
export interface ChatMessage extends PageChatMessage {
  citations?: Evidence[];
}

const ACTIVE_STATUSES = new Set(["uploaded", "processing"]);
const POLL_INTERVAL_MS = 2500;
/** Only the most recent turns are sent; the backend sees a bounded history. */
export const CHAT_HISTORY_LIMIT = 20;
/** Stored turns may exceed the sent window, but the rendered history never grows without bound. */
export const CHAT_STORE_LIMIT = CHAT_HISTORY_LIMIT * 2;

function chatKey(documentId: string, page: number): string {
  return `${documentId}:${page}`;
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return `${error.message}${error.requestId ? ` Request ${error.requestId}.` : ""}`;
  }
  return error instanceof Error ? error.message : "Unexpected error.";
}

function isAbort(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

/** A document still has work in flight while its status is active or its progress is incomplete. */
function isActiveAnalysis(response: AnalysisResponse): boolean {
  if (ACTIVE_STATUSES.has(response.document.status)) return true;
  const { page_count, processed_pages, failed_pages } = response.progress;
  return page_count > 0 && processed_pages + failed_pages < page_count;
}

export function useWorkbench() {
  const [documents, setDocuments] = useState<DocumentRecord[] | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [analyses, setAnalyses] = useState<Record<string, AnalysisResponse>>({});
  const [content, setContent] = useState<ArrayBuffer | null>(null);
  const [selectedPage, setSelectedPage] = useState(1);
  const [selectedCitation, setSelectedCitation] = useState<SelectedCitation | null>(null);
  const [libraryLoading, setLibraryLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [busy, setBusy] = useState<"upload" | "reanalyze" | null>(null);
  const [downloading, setDownloading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [chatSending, setChatSending] = useState(false);
  const [chatError, setChatError] = useState<{ page: number; message: string } | null>(null);
  const [chatVersion, setChatVersion] = useState(0);
  const chatsRef = useRef(new Map<string, ChatMessage[]>());
  const detailGeneration = useRef(0);
  const selectedIdRef = useRef(selectedId);
  const analysesRef = useRef(analyses);
  // Documents whose reanalysis was accepted but whose record still reads `completed`
  // until the leased worker picks the job up. The set keeps polling alive across that
  // gap; an id is dropped once the server shows fresh activity.
  const reanalyzeRequestedRef = useRef(new Set<string>());
  const [reanalyzeVersion, setReanalyzeVersion] = useState(0);

  useEffect(() => {
    selectedIdRef.current = selectedId;
  }, [selectedId]);

  useEffect(() => {
    analysesRef.current = analyses;
  }, [analyses]);

  const refreshLibrary = useCallback(async (quiet = false) => {
    if (!quiet) setLibraryLoading(true);
    try {
      const list = await api.documents();
      setDocuments(list);
      setSelectedId((current) => {
        if (current && list.some((item) => item.id === current)) return current;
        return list.find((item) => item.status === "completed")?.id ?? list[0]?.id ?? null;
      });
      if (!quiet) setError(null);
    } catch (reason) {
      if (!quiet) setError(errorMessage(reason));
    } finally {
      if (!quiet) setLibraryLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshLibrary();
  }, [refreshLibrary]);

  // Detail load for the selected document. Polling later updates `analyses` in place and
  // must never touch chat history or the selected page.
  useEffect(() => {
    const generation = ++detailGeneration.current;
    if (!selectedId) {
      setDetailLoading(false);
      return;
    }
    const controller = new AbortController();
    setDetailLoading(true);
    setError(null);
    setSelectedPage(1);
    setSelectedCitation(null);
    setContent(null);
    setChatError(null);
    Promise.all([api.analysis(selectedId, controller.signal), api.content(selectedId, controller.signal)])
      .then(([nextAnalysis, nextContent]) => {
        if (generation !== detailGeneration.current) return;
        setAnalyses((current) => ({ ...current, [selectedId]: nextAnalysis }));
        setContent(nextContent);
      })
      .catch((reason: unknown) => {
        if (isAbort(reason) || generation !== detailGeneration.current) return;
        setError(errorMessage(reason));
      })
      .finally(() => {
        if (generation === detailGeneration.current) setDetailLoading(false);
      });
    return () => controller.abort();
  }, [selectedId]);

  const pollTick = useCallback(async () => {
    let list: DocumentRecord[];
    try {
      list = await api.documents();
      setDocuments(list);
    } catch {
      return; // Transient failure; the next tick retries with the last known state.
    }
    const ids = new Set<string>();
    list.forEach((item) => {
      if (ACTIVE_STATUSES.has(item.status)) ids.add(item.id);
    });
    // Reanalysis keep-alives: the record still reads `completed` until the leased worker
    // picks the job up, so without these the fresh page results would never be polled in.
    reanalyzeRequestedRef.current.forEach((id) => ids.add(id));
    const selected = selectedIdRef.current;
    const selectedAnalysis = selected ? analysesRef.current[selected] : null;
    if (selected && selectedAnalysis && isActiveAnalysis(selectedAnalysis)) ids.add(selected);
    await Promise.all(
      [...ids].map(async (id) => {
        try {
          const response = await api.analysis(id);
          setAnalyses((current) => ({ ...current, [id]: response }));
          // Worker pickup or fresh progress means the normal active-state checks now
          // cover this document; drop the keep-alive.
          if (reanalyzeRequestedRef.current.has(id) && isActiveAnalysis(response)) {
            reanalyzeRequestedRef.current.delete(id);
            setReanalyzeVersion((version) => version + 1);
          }
        } catch {
          // Keep the previous partial analysis; the next tick retries.
        }
      }),
    );
  }, []);

  const hasActiveWork = useMemo(
    () => Boolean(documents?.some((item) => ACTIVE_STATUSES.has(item.status))),
    [documents],
  );
  const selectedAnalysis = selectedId ? (analyses[selectedId] ?? null) : null;
  const selectedAnalysisActive = selectedAnalysis ? isActiveAnalysis(selectedAnalysis) : false;

  useEffect(() => {
    // reanalyzeVersion re-evaluates the guard when a keep-alive is added or dropped,
    // since ref changes alone never re-run effects.
    if (!hasActiveWork && !selectedAnalysisActive && reanalyzeRequestedRef.current.size === 0) return;
    const timer = window.setInterval(() => void pollTick(), POLL_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [hasActiveWork, selectedAnalysisActive, reanalyzeVersion, pollTick]);

  const selectedDocument = useMemo(
    () => documents?.find((item) => item.id === selectedId) ?? selectedAnalysis?.document ?? null,
    [documents, selectedAnalysis, selectedId],
  );

  // Stable page order: pages may arrive in any order or be missing; sort by page number.
  const sortedPages = useMemo(
    () => (selectedAnalysis?.analysis?.pages ?? []).slice().sort((a, b) => a.page - b.page),
    [selectedAnalysis],
  );
  const pageByNumber = useMemo(
    () => new Map<number, PageAnalysis>(sortedPages.map((page) => [page.page, page])),
    [sortedPages],
  );
  const selectedPageAnalysis = pageByNumber.get(selectedPage) ?? null;

  const pageCount = useMemo(() => {
    if (selectedDocument?.page_count) return selectedDocument.page_count;
    const progressCount = selectedAnalysis?.progress.page_count ?? 0;
    if (progressCount > 0) return progressCount;
    return sortedPages.length > 0 ? sortedPages[sortedPages.length - 1].page : 1;
  }, [selectedDocument, selectedAnalysis, sortedPages]);

  useEffect(() => {
    if (selectedPage > pageCount) setSelectedPage(Math.max(1, pageCount));
  }, [pageCount, selectedPage]);

  const selectDocument = useCallback((documentId: string) => {
    setSelectedId(documentId);
    setError(null);
    setNotice(null);
  }, []);

  const selectPage = useCallback(
    (page: number) => {
      const clamped = Math.min(Math.max(1, page), Math.max(1, pageCount));
      setSelectedPage(clamped);
    },
    [pageCount],
  );

  const revealCitation = useCallback((citation: SelectedCitation) => {
    setSelectedCitation(citation);
    if (citation.evidence.page !== null) setSelectedPage(citation.evidence.page);
  }, []);

  const upload = useCallback(
    async (file: File) => {
      setBusy("upload");
      setError(null);
      setNotice(null);
      try {
        const result = await api.upload(file);
        await refreshLibrary(true);
        setSelectedId(result.document.id);
        setNotice(
          result.duplicate
            ? `Duplicate detected: opened the existing ${result.document.filename}; no new job was queued.`
            : `${result.document.filename} uploaded. Analysis job ${result.job_id ?? "queued"}.`,
        );
      } catch (reason) {
        setError(errorMessage(reason));
      } finally {
        setBusy(null);
      }
    },
    [refreshLibrary],
  );

  const reanalyze = useCallback(async (documentId: string) => {
    setBusy("reanalyze");
    setError(null);
    try {
      await api.reanalyze(documentId);
      // The record still reads `completed` until the leased worker picks the job up a few
      // seconds later; keep polling this id until the server shows fresh activity.
      reanalyzeRequestedRef.current.add(documentId);
      setReanalyzeVersion((version) => version + 1);
      setNotice("Reanalysis requested. Partial page results appear as the worker completes them.");
      const response = await api.analysis(documentId);
      setAnalyses((current) => ({ ...current, [documentId]: response }));
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(null);
    }
  }, []);

  const appendChat = useCallback((documentId: string, page: number, message: ChatMessage) => {
    const key = chatKey(documentId, page);
    const next = [...(chatsRef.current.get(key) ?? []), message].slice(-CHAT_STORE_LIMIT);
    chatsRef.current.set(key, next);
    setChatVersion((version) => version + 1);
  }, []);

  const chatHistory = useCallback(
    (page: number): ChatMessage[] => {
      if (!selectedId) return [];
      void chatVersion; // Subscribe to history changes without storing chat in state.
      return chatsRef.current.get(chatKey(selectedId, page)) ?? [];
    },
    [selectedId, chatVersion],
  );

  const sendChat = useCallback(
    async (page: number, content: string) => {
      const documentId = selectedIdRef.current;
      const trimmed = content.trim();
      if (!documentId || !trimmed || chatSending) return;
      const requestId = documentId;
      appendChat(documentId, page, { role: "user", content: trimmed });
      setChatSending(true);
      setChatError(null);
      const history = chatsRef.current.get(chatKey(requestId, page)) ?? [];
      const bounded = history.slice(-CHAT_HISTORY_LIMIT).map(({ role, content: text }) => ({ role, content: text }));
      try {
        const response = await api.pageChat(requestId, page, bounded);
        if (selectedIdRef.current !== requestId) return;
        appendChat(requestId, page, { role: "assistant", content: response.answer, citations: response.citations });
      } catch (reason) {
        if (isAbort(reason)) return;
        setChatError({ page, message: errorMessage(reason) });
      } finally {
        if (selectedIdRef.current === requestId) setChatSending(false);
      }
    },
    [appendChat, chatSending],
  );

  const retryChat = useCallback(
    (page: number) => {
      const documentId = selectedIdRef.current;
      if (!documentId) return;
      const key = chatKey(documentId, page);
      const history = chatsRef.current.get(key) ?? [];
      const last = history[history.length - 1];
      chatsRef.current.set(key, last && last.role === "user" ? history.slice(0, -1) : history);
      setChatVersion((version) => version + 1);
      setChatError(null);
      if (last && last.role === "user") void sendChat(page, last.content);
    },
    [sendChat],
  );

  const download = useCallback(
    async (target: "full" | "page", format: ExportFormat, page?: number) => {
      const document = selectedDocument;
      if (!document || downloading) return;
      const key = `${target}:${format}:${page ?? 0}`;
      setDownloading(key);
      setError(null);
      try {
        const blob =
          target === "full"
            ? await api.exportAnalysis(document.id, format)
            : await api.exportPage(document.id, page ?? 1, format);
        const stem = downloadStem(document.filename, document.id);
        const filename =
          target === "full" ? `${stem}-analysis.${format}` : `${stem}-page-${page ?? 1}.${format}`;
        downloadBlob(blob, filename);
        setNotice(`${filename} downloaded from the canonical backend analysis.`);
      } catch (reason) {
        setError(errorMessage(reason));
      } finally {
        setDownloading(null);
      }
    },
    [selectedDocument, downloading],
  );

  return {
    documents,
    selectedId,
    selectedDocument,
    analyses,
    selectedAnalysis,
    sortedPages,
    selectedPageAnalysis,
    pageCount,
    selectedPage,
    selectPage,
    content,
    selectedCitation,
    revealCitation,
    libraryLoading,
    detailLoading,
    busy,
    downloading,
    error,
    notice,
    selectDocument,
    refreshLibrary,
    upload,
    reanalyze,
    chatHistory,
    chatSending,
    chatError,
    sendChat,
    retryChat,
    download,
    clearError: () => setError(null),
    clearNotice: () => setNotice(null),
  };
}

export type Workbench = ReturnType<typeof useWorkbench>;
