// Mermaid init for the docs site: dark-slate theme, large readable text,
// generous box spacing (bigger boxes), securityLevel relaxed for labels.
mermaid.initialize({
  startOnLoad: true,
  securityLevel: "loose",
  theme: "base",
  themeVariables: {
    fontSize: "18px",
    fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
    primaryColor: "#1e293b",
    primaryTextColor: "#f1f5f9",
    primaryBorderColor: "#2dd4bf",
    lineColor: "#38bdf8",
    secondaryColor: "#0f172a",
    tertiaryColor: "#0f172a",
    clusterBkg: "#0f172a",
    edgeLabelBackground: "#0f172a",
  },
  flowchart: {
    nodeSpacing: 45,
    rankSpacing: 65,
    padding: 14,
    curve: "basis",
    htmlLabels: true,
  },
});
