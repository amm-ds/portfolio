// The apps block on the projects index: complete, lift-out-able production
// templates — full source (agent + API + frontend + infra), each with an
// article, screenshots, and downloadable specs. Static for now (one app);
// promote to a served registry when a second app needs dynamic behavior.

export interface AppEntry {
  id: string;
  title: string;
  /** One-paragraph what-it-is, client-facing. */
  summary: string;
  /** What an adopter gets, in house two-block style. */
  does: string;
  achieves: string;
  stack: string[];
  screenshot: string;
  links: { label: string; href: string }[];
}

export const APPS: AppEntry[] = [
  {
    id: "agent-chat",
    title: "chatbot agent — production template",
    summary:
      "A generic, modular agent you can lift out and adapt: typed tools and toolsets, disk-loaded skills, pgvector retrieval, human approval for consequential actions, and a streaming chat UI — the full path from clone to deployed service.",
    does: "pydantic-ai v2 agent (model-agnostic: local Ollama or hosted, with fallback), FastAPI streaming SSE, Postgres + pgvector memory and retrieval, React chat surface in the terminal design language",
    achieves: "swap the tools, keep the chassis — skills load from folders, providers switch by env, one command stands up the stack",
    stack: ["pydantic-ai", "FastAPI", "Postgres + pgvector", "React + TS", "docker compose"],
    screenshot: "/apps/agent-chat-approval.png",
    links: [
      { label: "[code]", href: "https://github.com/amm-ds/portfolio/tree/main/apps/agent-chat" },
      { label: "[article]", href: "https://amm-ds.github.io/portfolio/apps/chatbot-agent/" },
      { label: "[specs]", href: "https://github.com/amm-ds/portfolio/tree/main/apps/agent-chat/specs" },
    ],
  },
];

export const APPS_INTRO =
  "complete applications, built like client work — every one is a template: lift it out, swap the domain, ship it";
