import { useEffect, useRef, useState } from "react";

let initialized = false;
let diagramCounter = 0;

const MERMAID_THEME = {
  startOnLoad: false,
  theme: "base" as const,
  securityLevel: "strict" as const,
  fontFamily: '"JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, Consolas, monospace',
  themeVariables: {
    background: "transparent",
    fontSize: "18px",
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
    nodeSpacing: 45,
    rankSpacing: 65,
    padding: 14,
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
      try {
        const mermaid = (await import("mermaid")).default;
        if (!initialized) {
          mermaid.initialize(MERMAID_THEME);
          initialized = true;
        }
        const { svg } = await mermaid.render(`mmd-${diagramCounter++}`, code);
        if (cancelled || !hostRef.current) return;
        hostRef.current.innerHTML = svg;
        setReady(true);
      } catch {
        if (!cancelled) setFailed(true);
      }
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
