// Shared mermaid configuration. Single source of truth: MermaidDiagram.tsx
// initializes the runtime renderer with this, and scripts/render-diagrams.mjs
// reads + evals this file (stripping `as const`) so pre-rendered SVGs always
// match the live theme. Keep this file free of imports and runtime values.
export const MERMAID_THEME = {
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
