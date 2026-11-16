// The apps block on the projects index: complete, lift-out-able production
// templates — full source (agent + API + frontend + infra), each with an
// article, screenshots, and downloadable specs. The shared static registry is
// sufficient until applications need runtime-configured publication.

export interface AppEntry {
  id: string;
  title: string;
  /** Internal article route — the whole card title links here. */
  href: string;
  /** One-paragraph what-it-is, client-facing. */
  summary: string;
  /** What an adopter gets, in house two-block style. */
  does: string;
  achieves: string;
  stack: string[];
  /** Evidence shown in the shared green result chip. */
  result: string;
  screenshot: string;
  links: { label: string; href: string }[];
}

export const APPS: AppEntry[] = [
  {
    id: "agent-chat",
    title: "Chatbot Agent — Production Template",
    href: "/apps/agent-chat",
    summary:
      "A generic, modular agent you can lift out and adapt: typed tools and toolsets, disk-loaded skills, pgvector retrieval, human approval for consequential actions, and a streaming chat UI — the full path from clone to deployed service.",
    does: "pydantic-ai v2 agent (Kimi, local Ollama or hosted, with fallback), FastAPI streaming SSE, Postgres + pgvector memory and retrieval, React chat surface in the terminal design language",
    achieves: "swap the tools, keep the chassis — skills load from folders, providers switch by env, one command stands up the stack",
    stack: ["pydantic-ai", "FastAPI", "Postgres + pgvector", "React + TS", "docker compose"],
    result: "108/108 Kimi eval ×3",
    screenshot: "/apps/agent-chat-approval-v3.png",
    links: [
      { label: "[code]", href: "https://github.com/amm-ds/portfolio/tree/main/apps/agent-chat" },
      { label: "[specs]", href: "https://github.com/amm-ds/portfolio/tree/main/apps/agent-chat/specs" },
    ],
  },
  {
    id: "document-intelligence",
    title: "AI Document Intelligence Workbench",
    href: "/apps/document-intelligence",
    summary:
      "A page-level PDF analysis workbench: one AI call per page produces a cited summary, typed entities, and topics, with a fourth page-scoped chat mode — every claim parser-resolved to its exact source.",
    does: "FastAPI + separate leased worker, per-page Pydantic AI structured output, PyMuPDF evidence coordinates, page-by-page progress with partial pages visible, and a React workbench with JSON/Markdown reports",
    achieves: "read a PDF page by page with AI — verify every citation deterministically, watch pages complete, and download full or selected-page reports",
    stack: ["pydantic-ai", "FastAPI", "Postgres", "React + TS", "PyMuPDF"],
    result: "page-level · 4 AI modes",
    screenshot: "/apps/document-intelligence-summary.png",
    links: [
      { label: "[code]", href: "https://github.com/amm-ds/portfolio/tree/main/apps/document-intelligence" },
      { label: "[specs]", href: "https://github.com/amm-ds/portfolio/tree/main/apps/document-intelligence/specs" },
    ],
  },
];

export const APPS_INTRO =
  "complete applications, built like client work — every one is a template: lift it out, swap the domain, ship it";
