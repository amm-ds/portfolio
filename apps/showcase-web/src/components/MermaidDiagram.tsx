import { useEffect, useRef, useState } from "react";

let initialized = false;
let diagramCounter = 0;
// mermaid.render mutates shared temp DOM internally and is not safely
// reentrant: concurrent renders (multiple diagrams on one page) throw
// intermittently in Safari. Serialize every render through this queue.
let renderQueue: Promise<unknown> = Promise.resolve();

function renderQueued(id: string, code: string): Promise<{ svg: string }> {
  const run = async (): Promise<{ svg: string }> => {
    const mermaid = (await import("mermaid")).default;
    if (!initialized) {
      mermaid.initialize(MERMAID_THEME);
      initialized = true;
    }
    return mermaid.render(id, code);
  };
  const result = renderQueue.then(run, run);
  renderQueue = result.catch(() => undefined);
  return result;
}

const MERMAID_THEME = {
  startOnLoad: false,
  theme: "base" as const,
  securityLevel: "strict" as const,
  fontFamily: '"JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, Consolas, monospace',
  themeVariables: {
    background: "transparent",
    fontSize: "20px",
    primaryColor: "#1e293b",
    primaryTextColor: "#f1f5f9",
    primaryBorderColor: "#2dd4bf",
    secondaryColor: "#0f172a",
    secondaryTextColor: "#e2e8f0",
    secondaryBorderColor: "#334155",
    tertiaryColor: "#1e293b",
    tertiaryTextColor: "#94a3b8",
    tertiaryBorderColor: "#334155",
    lineColor: "#38bdf8",
    textColor: "#e2e8f0",
    mainBkg: "#1e293b",
    nodeBorder: "#2dd4bf",
    clusterBkg: "#0f172a",
    clusterBorder: "#334155",
    titleColor: "#e2e8f0",
    edgeLabelBackground: "#0f172a",
    fontFamily: '"JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, Consolas, monospace',
  },
  // Bigger boxes + generous spacing so labels stay readable; matches
  // docs/assets/mermaid-init.js.
  flowchart: {
    useMaxWidth: true,
    nodeSpacing: 55,
    rankSpacing: 85,
    padding: 20,
    htmlLabels: true,
    curve: "basis" as const,
  },
};

/**
 * Lazy-rendered mermaid diagram. The mermaid chunk loads on first use;
 * parse/render failures fall back to a styled <pre> of the source — the page
 * never crashes on a bad diagram.
 */
export function MermaidDiagram({ code }: { code: string }) {
  const hostRef = useRef<HTMLDivElement>(null);
  const [failed, setFailed] = useState(false);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      // one retry before falling back: transient failures (observer timing,
      // chunk still warming) should not dump raw source on the page
      for (let attempt = 0; attempt < 2; attempt += 1) {
        try {
          const { svg } = await renderQueued(`mmd-${diagramCounter++}`, code);
          if (cancelled || !hostRef.current) return;
          hostRef.current.innerHTML = svg;
          setReady(true);
          return;
        } catch {
          if (cancelled) return;
        }
      }
      if (!cancelled) setFailed(true);
    })();
    return () => {
      cancelled = true;
    };
  }, [code]);

  if (failed) {
    return (
      <pre className="code-block mermaid-fallback">
        <code>{code}</code>
      </pre>
    );
  }

  return (
    <div className="mermaid-wrap">
      {!ready && (
        <div className="frame-skeleton" aria-hidden="true">
          <span>rendering diagram…</span>
        </div>
      )}
      <div ref={hostRef} className="mermaid-host" data-testid="mermaid-host" />
    </div>
  );
}
