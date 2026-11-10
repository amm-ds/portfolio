import type { ReactNode } from "react";
import { AppArticleSection, AppScreenshot as Screenshot } from "../components/AppArticle";
import { Card } from "../components/Card";
import { LazyFlowDiagram } from "../components/diagrams/LazyFlowDiagram";
import { useScrollSpy } from "../hooks/useScrollSpy";
import { renderMarkdown } from "../lib/markdown";
import { usePageMeta } from "../seo";

const REPO = "https://github.com/amm-ds/portfolio/tree/main/apps/agent-chat";

const TOOL_SNIPPET = `\`\`\`python
async def send_message(ctx: RunContext[ChatDeps], subject: str, body: str) -> str:
    """Send a team message. CONSEQUENTIAL: requires human approval."""
    summary = f"{subject}: {body[:160]}"
    if not await ctx.deps.approvals.request("send_message", summary):
        return "Message NOT sent: denied by operator."
    # Provider call happens only after explicit approval.
    ...
\`\`\``;

const PROVIDER_SNIPPET = `\`\`\`bash
export AGENT_CHAT_PROVIDER=kimi
export AGENT_CHAT_KIMI_BASE_URL=https://api.kimi.com/coding/v1
export AGENT_CHAT_KIMI_API_KEY=<secret>
export AGENT_CHAT_KIMI_MODEL=kimi-for-coding
# No agent, tool, API, or UI changes are required.
\`\`\``;

const SSE_SNIPPET = `\`\`\`json
{"type":"approval_request","approval_id":"9f2c71ab05d3","tool":"send_message","summary":"Weekly report"}
{"type":"approval_response","approval_id":"9f2c71ab05d3","approved":true}
{"type":"done","answer":{"text":"…","citations":[],"uncertainty":"low"},"usage":{"input_tokens":842,"output_tokens":117,"requests":3},"conversation_id":"0192f8d4-a7b2-7c1e-8f3a-2d9c6b1a4e55"}
\`\`\``;

const EVAL_SNIPPET = `\`\`\`bash
cd apps/agent-chat
uv run pytest -q
uv run python -m agent_chat.evals.runner
uv run python -m agent_chat.evals.runner --model real
\`\`\``;

const SKILL_SNIPPET = `\`\`\`text
src/agent_chat/skills/
└── handbook/
    ├── SKILL.md          # first paragraph = model-facing description
    └── resources/
        └── policies.md   # deterministic search_handbook tool
\`\`\``;

const SPECS = [
  {
    title: "architecture",
    text: "Component boundaries, request lifecycle, provider/store protocols, and deployment topology.",
    href: `${REPO}/specs/architecture.md`,
  },
  {
    title: "operations",
    text: "Configuration, health checks, failure modes, and the commands needed to operate the stack.",
    href: `${REPO}/specs/operations.md`,
  },
  {
    title: "adapting",
    text: "Concrete swap points for providers, tools, skills, retrieval, storage, UI styling, and deployment.",
    href: `${REPO}/specs/adapting.md`,
  },
  {
    title: "decision records",
    text: "Six ADRs covering the agent, approval, session memory, retrieval, and frontend choices and their limits.",
    href: `${REPO}/specs/decisions`,
  },
];

const SECTIONS = [
  { id: "background", title: "Background" },
  { id: "objectives", title: "Objectives" },
  { id: "architecture", title: "Architecture" },
  { id: "interface", title: "Interface" },
  { id: "memory", title: "Memory" },
  { id: "evaluation", title: "Evaluation" },
  { id: "specs", title: "Specs" },
  { id: "adapt", title: "Adapt & limits" },
] as const;

function ArticleSection(props: {
  id: string;
  index: number;
  subtitle: string;
  takeaway: string;
  children: ReactNode;
}) {
  return <AppArticleSection {...props} title={SECTIONS[props.index - 1].title} />;
}

export function AgentChatArticle() {
  usePageMeta({
    title: "Chatbot agent — production template",
    description:
      "A lift-out agent chassis with typed tools, disk-loaded skills, pgvector retrieval, durable memory, human approvals, deterministic evaluation, and a streaming React UI.",
    canonical: "/apps/agent-chat",
  });
  const active = useScrollSpy(SECTIONS.map((section) => section.id));

  return (
    <>
      <header className="detail-header">
        <p className="kicker">&gt; apps / agent-chat</p>
        <h1>Chatbot agent — production template</h1>
        <p className="detail-lead">
          A modular agent you can lift out and adapt: typed tools and toolsets, disk-loaded
          skills, pgvector retrieval, durable memory, human approval for consequential actions,
          and a streaming chat UI.
        </p>
        <div className="chips" aria-label="Technology stack">
          {["Agentic AI", "FastAPI", "Postgres + pgvector", "React + TypeScript"].map((tech) => (
            <span key={tech} className="chip">{tech}</span>
          ))}
        </div>
        <div className="meta-links">
          <a className="chip-link" href={REPO} target="_blank" rel="noopener noreferrer">[source]</a>
          <a className="chip-link" href={`${REPO}/specs`} target="_blank" rel="noopener noreferrer">[specs]</a>
        </div>
      </header>
      <div className="story-layout">
        <nav className="rail" aria-label="App article sections">
          <span className="rail-label">index</span>
          {SECTIONS.map((section, index) => (
            <a
              key={section.id}
              href={`#${section.id}`}
              className={active === section.id ? "active" : ""}
              aria-current={active === section.id ? "location" : undefined}
            >
              <span className="rail-num">{String(index + 1).padStart(2, "0")}</span>
              {section.title.toLowerCase()}
            </a>
          ))}
        </nav>
        <div>
          <ArticleSection
            id="background"
            index={1}
            subtitle="a lift-out chassis for real assistants, not a chat screenshot"
            takeaway="One repository carries the agent, streaming API, React UI, Postgres storage, eval suite, and deployment files — adapt behind five explicit seams: provider, embedder, vector store, notebook, approval gate."
          >
            <div className="prose">
              <p>
                Agent Chat packages the path from a user message to a cited, persisted answer.
                The same codebase contains the agent, API, React surface, storage adapters,
                evaluation suite, and deployment files. The seams are explicit: model provider,
                embedder, vector store, notebook, and approval gate.
              </p>
              <ul>
                <li>One <code>build_agent</code> assembly point with structured <code>Answer</code> output and per-run usage budgets.</li>
                <li>Typed toolsets and deferred skills loaded from folders, not a monolithic prompt.</li>
                <li>FastAPI streaming, request IDs, structured errors, and health/readiness endpoints.</li>
                <li>React conversation UI with tool traces, citations, and approval cards.</li>
              </ul>
              <p>
                <strong>The handoff boundary is deliberate.</strong> The repository includes the
                application chassis, local and containerized startup, sample tools and documents,
                and executable contracts. The adopter supplies the domain corpus, credentials,
                identity provider, production SLOs, retention policy, and model acceptance threshold.
                A successful demo is the starting point for validation, not proof of unattended readiness.
              </p>
            </div>
          </ArticleSection>

          <ArticleSection
            id="objectives"
            index={2}
            subtitle="typed tools, bounded runs, and explicit side effects"
            takeaway="The model proposes actions; the runtime decides. Typed tools own their schema, per-run budgets stop loops, and a consequential tool cannot fire before the human approval gate resolves."
          >
            <div className="prose">
              <p>
                Tools own their model-facing schema through typed functions and docstrings.
                Consequential tools use the same approval protocol as the demo <code>send_message</code>
                tool: no provider call or external side effect occurs before the gate resolves.
              </p>
            </div>
            {renderMarkdown(TOOL_SNIPPET)}
            <div className="prose">
              <p>
                The agent finishes with a validated <code>Answer</code> containing text, citations,
                and uncertainty. Request and token budgets stop runaway loops; output-validation
                retries are separate from provider fallback.
              </p>
              <p>
                This single-agent shape fits support copilots, internal knowledge assistants, and
                operator-approved workflows with a bounded tool inventory. Choose durable execution
                or explicit multi-agent orchestration instead when work spans hours, independent
                workers, or separately owned failure domains; do not hide that complexity in a larger prompt.
              </p>
            </div>
          </ArticleSection>

          <ArticleSection
            id="architecture"
            index={3}
            subtitle="provider, retrieval, memory, and approval boundaries stay independent"
            takeaway="Swap the model with four environment variables — Kimi, local Ollama, or any OpenAI-compatible API. Fallback covers provider failures, retries cover schema failures, and browser sessions are isolated by construction."
          >
            <LazyFlowDiagram specId="app-agent-chat-architecture" />
            <div className="prose">
              <p>
                Retrieval returns source-addressed passages. The model sees only relevant tools
                and deferred skill descriptions, then produces the structured output. Provider
                selection lives in one factory and supports Kimi, local Ollama, generic
                OpenAI-compatible APIs, and optional fallback chains.
              </p>
              <ul>
                <li><strong>Owned execution:</strong> the API creates one bounded <code>UseThreadExecutor</code> for synchronous agent callbacks and closes it during FastAPI lifespan shutdown, alongside the stores.</li>
                <li><strong>Different failure policies:</strong> fallback handles provider API failures; <code>model_retries</code> handles output-validation failures. Neither is a substitute for the other.</li>
                <li><strong>Isolated runs:</strong> each browser session owns its conversations, notebook, and approval decisions; one session cannot read or settle another session's state.</li>
              </ul>
            </div>
            {renderMarkdown(PROVIDER_SNIPPET)}
            <LazyFlowDiagram specId="auto-app-agent-chat-1" />
            <div className="prose">
              <p>
                Pydantic AI also provides <a href="https://ai.pydantic.dev/deferred-tools/" target="_blank" rel="noopener noreferrer">native deferred tools</a>:
                a run can return <code>DeferredToolRequests</code> and later resume from saved history
                with <code>DeferredToolResults</code>. That model is a better fit for long-running or
                cross-process work. This template keeps its explicit gate because the interactive UI
                needs approval events on the same continuous SSE stream while the current run waits;
                the trade-off is that pending approvals live in the API process, not a durable workflow store.
              </p>
            </div>
          </ArticleSection>

          <ArticleSection
            id="interface"
            index={4}
            subtitle="streamed answers, visible tool work, and an operator decision in-band"
            takeaway="One SSE stream carries the answer, tool traces, citations, and approval cards; /health names the provider and model, /ready probes both stores, and every response carries an X-Request-ID."
          >
            <div className="app-media-grid">
              <Screenshot
                name="agent-chat-ui-v3.png"
                alt="Agent chat interface with conversation sidebar, streamed response, tool calls and citations"
                caption="Streamed answer, tool calls, and citations in the main workspace."
              />
              <Screenshot
                name="agent-chat-approval-v3.png"
                alt="Agent chat waiting for an operator to approve or deny a send_message action"
                caption="The run pauses for an explicit approve/deny decision."
              />
            </div>
            <div className="app-video">
              <video controls preload="metadata" playsInline poster="/apps/agent-chat-ui-v3.png">
                <source src="/apps/agent-chat-demo.webm" type="video/webm" />
                <source src="/apps/agent-chat-demo.mp4" type="video/mp4" />
                <track
                  kind="captions"
                  src="/apps/agent-chat-demo.vtt"
                  srcLang="en"
                  label="English scene descriptions"
                  default
                />
                Your browser does not support the video element.
              </video>
              <div className="prose">
                <p>
                  <strong>Walkthrough:</strong> a question streams an answer with tool evidence,
                  a consequential action pauses for approval, and a later conversation recalls a
                  stored fact. The clip uses the same public UI and typed SSE contract shown below.
                </p>
                <p>
                  The WebM and MP4 come from the same clean 44.8-second browser recording against
                  <code>kimi-for-coding</code>, with fresh conversations rather than mock transport.
                  The recorder now waits for a new run's final usage and validates the complete memory
                  acknowledgement and recall before publishing. Versioned screenshots and matching
                  scene captions keep the evidence reproducible and prevent stale cached results.
                </p>
              </div>
            </div>
            {renderMarkdown(SSE_SNIPPET)}
            <div className="prose">
              <p>
                <code>GET /health</code> reports liveness plus the configured provider and primary
                model; <code>GET /ready</code> separately probes both stores. Every HTTP response
                carries <code>X-Request-ID</code>, ordinary errors use a structured envelope containing
                that id, and streaming failures become typed <code>error</code> events before the stream closes.
              </p>
              <p>
                The API retains the typed <code>uncertainty</code> field for schema and evaluation
                compatibility, but the chat surface intentionally does not display it. A model-generated
                label is not calibrated evidence; citations, tool results, and measured eval behavior
                communicate reliability more honestly.
              </p>
            </div>
          </ArticleSection>

          <ArticleSection
            id="memory"
            index={5}
            subtitle="session-scoped facts without turning every prompt into a transcript"
            takeaway="Notebook facts live in the browser session: new chats in the same tab recall up to five notes (hard cap ten) with atomic replacement; another session's conversations, memory, and approvals return 404."
          >
            <div className="prose">
              <p>
                Conversation history belongs to one <code>conversation_id</code>. Notebook facts
                belong to an anonymous UUID in <code>sessionStorage</code>: new conversations and
                reloads in the same tab share them, while closing the tab starts a fresh namespace.
                No account or user-management UI is required.
              </p>
              <ul>
                <li><strong>Per conversation:</strong> the last 10 user turns remain by default, including tool legs. Overflow can be summarized; recent turns stay verbatim.</li>
                <li><strong>Per browser session:</strong> the notebook persists concise facts with atomic replacement. Stable keys such as <code>preferred_cloud</code> upsert changed preferences instead of accumulating paraphrase duplicates.</li>
                <li><strong>Bounded and untrusted:</strong> recall returns five notes by default, hard-bounded at ten. It never injects the whole notebook or treats recalled text as instructions.</li>
                <li><strong>Isolated by default:</strong> conversations, memory, and approval decisions from another session return 404.</li>
              </ul>
              <p>
                The session header is an isolation label, not authentication or secure deletion.
                Production deployments must derive tenant identity from the authenticated principal,
                use transactional stores for concurrent writers, and schedule retention cleanup for
                old notebook files and conversation rows. An append-only transcript remains a separate
                choice when audit obligations include trimmed turns.
              </p>
            </div>
            <div className="app-media-grid app-media-grid--single">
              <Screenshot
                name="agent-chat-memory-v3.png"
                alt="Agent chat recalling one cloud preference in the current browser session"
                caption="One complete fact is recalled in a new conversation within the same browser session."
              />
            </div>
          </ArticleSection>

          <ArticleSection
            id="evaluation"
            index={6}
            subtitle="deterministic graders offline, the same suite against a real provider"
            takeaway="Sixteen scripted cases, exact graders, no judges — 108/108 assertions passed in each of three kimi-for-coding runs, with denials, verbatim citations, and cross-conversation memory graded separately."
          >
            <div className="prose">
              <p>
                A 16-case suite uses scripted fake models for deterministic CI. Exact tool-set
                assertions replace subjective judging; refusal probes cover prompt leaks,
                unsupported requests, and financial actions. A complete memory acknowledgement is
                graded separately from recall in a fresh conversation.
              </p>
            </div>
            {renderMarkdown(EVAL_SNIPPET)}
            <div className="prose">
              <p>
                The real-model path runs the same cases and graders against the configured provider.
                The runner writes a Markdown report with model identity, per-case verdicts, and failure diagnostics.
              </p>
              <p>
                <strong>Measured result with <code>kimi-for-coding</code>: 108/108 assertions passed in each of three repetitions.</strong>{" "}
                The release gate covers exact tools and message text, denied side effects, verbatim
                evidence citations, cross-conversation memory, graceful refusals, and zero unnecessary
                tool calls. Grounded citation repair selects only exact retrieved text; it cannot invent
                a source or quote.
              </p>
              <ul>
                <li>Run provider-specific regression gates after model, prompt, tool, or retrieval changes.</li>
                <li>Review the failed answers before deciding whether to fix the system or refine an incorrect expectation.</li>
                <li>Keep consequential actions supervised until the deployed provider meets an explicit acceptance threshold.</li>
              </ul>
              <p>
                <a href={`${REPO}/reports/evals-kimi-for-coding.md`} target="_blank" rel="noopener noreferrer">
                  read the measured report →
                </a>{" · "}
                <a href={`${REPO}/src/agent_chat/evals`} target="_blank" rel="noopener noreferrer">
                  inspect eval cases and graders →
                </a>
              </p>
            </div>
          </ArticleSection>

          <ArticleSection
            id="specs"
            index={7}
            subtitle="architecture, operations, adaptation, and decisions ready to download"
            takeaway="Four specs and six ADRs document boundaries, operations, swap points, and trade-offs; the handoff checklist puts an authenticated gateway in front before any real tenant."
          >
            <div className="app-spec-grid">
              {SPECS.map((spec) => (
                <Card key={spec.title} className="app-spec-card">
                  <span className="study-block-label">spec</span>
                  <h3>{spec.title}</h3>
                  <p>{spec.text}</p>
                  <a href={spec.href} target="_blank" rel="noopener noreferrer">open spec →</a>
                </Card>
              ))}
            </div>
            <div className="prose">
              <p><strong>Production handoff checklist</strong></p>
              <ul>
                <li>Put an authenticated gateway in front of chat and mutations; derive tenant identity from its principal and never expose privileged keys through <code>VITE_*</code> assets.</li>
                <li>Keep provider credentials, database URLs, and API keys in the host secret manager; keep FastAPI and Postgres on a private network behind TLS.</li>
                <li>Disable SSE response buffering and caching at the proxy, and set read timeouts that cover provider latency plus the human approval window.</li>
                <li>Use readiness for rollout gates, automated and tested Postgres backups for recovery, and request-id-correlated logs and traces for diagnosis.</li>
                <li>Retain the previous image and a compatible database snapshot so application rollback does not depend on rebuilding the model or vector store.</li>
              </ul>
            </div>
          </ArticleSection>

          <ArticleSection
            id="adapt"
            index={8}
            subtitle="change identity, capabilities, and infrastructure in that order"
            takeaway="Adapt instructions first, then add tools or skill folders; provider, embedder, and store swaps stay behind protocols. MCP is optional — every toolset answers to the same approval and refusal policy."
          >
            <div className="prose">
              <p>
                Edit <code>BASE_INSTRUCTIONS</code> first, preserving tool discipline and escalation
                rules. Add a typed tool or a skill folder next; provider, embedder, vector store,
                and database swaps stay behind their protocols.
              </p>
            </div>
            {renderMarkdown(SKILL_SNIPPET)}
            <div className="prose">
              <p>
                MCP is an optional integration choice, not a prerequisite: attach an MCP toolset
                behind the same tool boundary when an existing server is useful, and apply the same
                approval and refusal policies to consequential operations. Adding more tools does not
                remove the need for scoped credentials and provider-specific evals.
              </p>
              <p>
                Pydantic AI emits OpenTelemetry traces for agent runs, model requests, and tool calls;
                follow the official <a href="https://ai.pydantic.dev/observability/" target="_blank" rel="noopener noreferrer">observability guidance</a> to
                instrument the deployed stack. For sensitive deployments, use content exclusion so
                prompts, completions, tool arguments, and tool results stay out of telemetry while
                structural timing and usage data remain available. Raw HTTP capture needs a separate
                privacy review and should stay off for sensitive traffic.
              </p>
              <p>
                <strong>Limits:</strong> this is a single-agent chassis, not multi-agent
                orchestration. It does not ship your domain corpus, credentials, production SLOs,
                or a hosted model. Those choices belong to the adopter and are explicit in the
                operations guide.
              </p>
              <p>
                <a href={`${REPO}/README.md`} target="_blank" rel="noopener noreferrer">
                  start with the app README →
                </a>
              </p>
            </div>
          </ArticleSection>
        </div>
      </div>
    </>
  );
}
