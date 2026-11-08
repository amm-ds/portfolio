import type { DiagramSpec } from "./types";

// Facts: apps/agent-chat/{specs/architecture.md,README.md,reports/evals-kimi-for-coding.md}.
export const AGENT_CHAT_ARCHITECTURE_SPEC = {
  id: "app-agent-chat-architecture",
  title: "Message → agent → typed SSE: the chat agent chassis",
  direction: "LR",
  canvasHeight: 560,
  nodes: [
    {
      id: "ui",
      label: "React chat UI",
      kind: "source",
      facts: [
        "The Vite + React UI consumes the SSE stream and the conversations API; its decoder mirrors the canonical wire contract in api/events.py.",
        "One anonymous X-Agent-Chat-Session UUID per browser tab, created in sessionStorage; closing the tab starts a fresh namespace.",
      ],
    },
    {
      id: "api",
      label: "FastAPI surface · typed SSE",
      kind: "api",
      facts: [
        "POST /chat streams typed events (text_delta, tool_call_start/end, approval_request/response, done, error); tool results are capped at 500 chars.",
        "Every response carries X-Request-ID; errors use the structured {error: {code, message, request_id}} envelope.",
      ],
    },
    {
      id: "agent",
      label: "pydantic-ai agent · typed Answer + budgets",
      kind: "agent",
      facts: [
        "build_agent wires BASE_INSTRUCTIONS, the structured Answer output, toolsets, deferred skills, the history processor, and per-run UsageLimits into one pydantic-ai Agent.",
        "Per-run budgets come from config.py: request/token usage limits, approval_timeout_s, model_retries, and executor_workers (default four).",
      ],
    },
    {
      id: "model",
      label: "model provider · one factory",
      kind: "model",
      facts: [
        "models.py is the only provider seam: Ollama by default, a hosted OpenAI-compatible API, or Kimi, with an optional fallback chain.",
        "Kimi coding-endpoint model ids include k3-256k, kimi-for-coding, and k3.1-pro.",
      ],
    },
    {
      id: "tools",
      label: "typed tools + disk-loaded skills",
      kind: "tool",
      facts: [
        "tools/ are typed functions whose docstring is the model-facing schema: calculator, clock, fetch_url (opt-in network), and send_message (the HITL demo).",
        "skills/ are disk folders (handbook/, summarize/); a folder with resources/ gets a search_<name> tool, disclosed progressively.",
      ],
    },
    {
      id: "rag",
      label: "retrieval · chunk + embed + retrieve",
      kind: "tool",
      facts: [
        "rag/ chunks paragraph-first (at most 500 chars, 50-char overlap), embeds with MiniLM, and exposes a bound retrieve tool plus the ingest CLI.",
        "rag_chunks stores VECTOR(384) embeddings behind an HNSW cosine index (m = 16, ef_construction = 64).",
      ],
    },
    {
      id: "memory",
      label: "session memory · conversations + notebook",
      kind: "data",
      facts: [
        "conversations.py persists whole Conversations (Postgres primary, SQLite fallback); history.py keeps the last 10 user turns by default.",
        "notebook.py keeps one JSON file per browser session; recall returns 5 notes by default, hard-bounded at 10, with no automatic notebook injection.",
      ],
    },
    {
      id: "db",
      label: "Postgres 16 + pgvector",
      kind: "data",
      facts: [
        "Compose brings up Postgres 16 + pgvector; database_url selects it over the stdlib-SQLite fallback with the same row shapes.",
      ],
    },
    {
      id: "gate",
      label: "approval gate · consequential action?",
      kind: "gate",
      facts: [
        "Any consequential tool goes through the ApprovalGate protocol; AutoApproval (evals) and DenyAll (audit paths) ship as implementations.",
        "The SSE gate mints a 12-hex approval id and parks the run on asyncio.wait_for(future, timeout_s).",
        "No answer within AGENT_CHAT_APPROVAL_TIMEOUT_S (default 120 s) means denied; implementations never raise for a missing answer.",
      ],
    },
    {
      id: "human",
      label: "approve / deny card · in-band",
      kind: "gate",
      facts: [
        "approval_request / approval_response events ride the run's own SSE stream; POST /approvals/{id} with the session header settles the future.",
        "Each run gets its own gate bound to its own queue and session, so concurrent chats never cross approval streams or decisions.",
      ],
    },
    {
      id: "out",
      label: "typed SSE response out",
      kind: "output",
      facts: [
        "The done event carries the typed Answer, a usage summary, and the conversation_id; the persisted title is the first 60 chars of the prompt.",
        "Exceptions become typed error events (code = exception class name in snake_case) before the data: [DONE] terminator.",
        "Measured with kimi:kimi-for-coding: 108/108 grader assertions passed in each of 3 repetitions across the 16-case suite (reports/evals-kimi-for-coding.md).",
      ],
    },
  ],
  edges: [
    { id: "ui-api", source: "ui", target: "api", kind: "task", label: "POST /chat (SSE)" },
    { id: "api-agent", source: "api", target: "agent", kind: "task", label: "run_stream_events" },
    { id: "agent-model", source: "agent", target: "model", kind: "task", label: "model request" },
    { id: "model-agent", source: "model", target: "agent", kind: "result", label: "text + usage" },
    { id: "agent-tools", source: "agent", target: "tools", kind: "task", label: "typed tool call" },
    { id: "tools-agent", source: "tools", target: "agent", kind: "result", label: "result" },
    { id: "agent-rag", source: "agent", target: "rag", kind: "task", label: "retrieve" },
    { id: "rag-db", source: "rag", target: "db", kind: "task", label: "chunks + vectors" },
    { id: "rag-agent", source: "rag", target: "agent", kind: "result", label: "passages" },
    { id: "agent-memory", source: "agent", target: "memory", kind: "task", label: "recall + history" },
    { id: "memory-db", source: "memory", target: "db", kind: "task", label: "conversations" },
    { id: "memory-agent", source: "memory", target: "agent", kind: "result", label: "bounded turns + notes" },
    { id: "agent-gate", source: "agent", target: "gate", kind: "task", label: "consequential tool" },
    { id: "gate-human", source: "gate", target: "human", kind: "task", label: "approval required" },
    { id: "gate-out", source: "gate", target: "out", kind: "result", label: "safe output" },
    { id: "human-agent", source: "human", target: "agent", kind: "task", label: "approve: resume run" },
    { id: "human-out", source: "human", target: "out", kind: "error", label: "deny / timeout" },
  ],
} as const satisfies DiagramSpec;
