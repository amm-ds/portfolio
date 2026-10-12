import { useRef, useState } from "react";
import { streamChat, type ChatResult } from "../api";
import { CitationCard } from "../components/CitationCard";

interface Turn {
  role: "user" | "assistant";
  text: string;
  result?: ChatResult;
  error?: boolean;
}

const EXAMPLE_QUESTIONS = [
  "What retrieval strategy does the RAG agent use?",
  "How is evaluation measured in project 01?",
  "Which chunking settings are used?",
];

export function RAGChat() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const abortRef = useRef<(() => void) | null>(null);

  async function ask(question: string) {
    const q = question.trim();
    if (!q || busy) return;
    setTurns((prev) => [...prev, { role: "user", text: q }]);
    setInput("");
    setBusy(true);
    setStatus("Connecting…");

    setTurns((prev) => [...prev, { role: "assistant", text: "" }]);

    const abort = await streamChat(q, {
      onDelta: (delta) => {
        setStatus("Streaming…");
        setTurns((prev) =>
          prev.map((t, i) => (i === prev.length - 1 && t.role === "assistant" ? { ...t, text: t.text + delta } : t)),
        );
      },
      onResult: (result) => {
        setStatus(null);
        setTurns((prev) =>
          prev.map((t, i) =>
            i === prev.length - 1 && t.role === "assistant" ? { ...t, result } : t,
          ),
        );
        setBusy(false);
        abortRef.current = null;
      },
      onError: (message) => {
        setStatus(null);
        setTurns((prev) => {
          const copy = [...prev];
          const last = copy[copy.length - 1];
          copy[copy.length - 1] = last.role === "assistant"
            ? { ...last, text: last.text || `Error: ${message}`, error: true }
            : last;
          return copy;
        });
        setBusy(false);
        abortRef.current = null;
      },
    });
    abortRef.current = abort;
  }

  function stop() {
    abortRef.current?.();
    abortRef.current = null;
    setBusy(false);
    setStatus("Stopped.");
  }

  return (
    <>
      <h1>RAG demo</h1>
      <p className="chat-note">
        Ask questions about this portfolio's RAG agent project. The demo runs offline with a
        deterministic mock provider unless LLM credentials are configured on the server.
      </p>

      <div className="chat-log">
        {turns.map((turn, i) => (
          <div key={i} className={`chat-message ${turn.role}${turn.error ? " error" : ""}`}>
            {turn.text}
            {turn.result && (
              <>
                <div className="citations">
                  {turn.result.citations.map((c) => (
                    <CitationCard key={c.chunk_id} citation={c} />
                  ))}
                </div>
                <p className="confidence">
                  Confidence: {turn.result.confidence.toFixed(2)}
                </p>
              </>
            )}
          </div>
        ))}
        {status && <p className="chat-status">{status}</p>}
      </div>

      <form
        className="chat-form"
        onSubmit={(e) => {
          e.preventDefault();
          void ask(input);
        }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a question about the RAG project…"
          aria-label="Question"
          disabled={busy}
        />
        {busy ? (
          <button type="button" onClick={stop}>
            Stop
          </button>
        ) : (
          <button type="submit" disabled={!input.trim()}>
            Send
          </button>
        )}
      </form>

      <div className="examples">
        {EXAMPLE_QUESTIONS.map((q) => (
          <button key={q} type="button" disabled={busy} onClick={() => void ask(q)}>
            {q}
          </button>
        ))}
      </div>
    </>
  );
}
