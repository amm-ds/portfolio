import type { ReactNode } from "react";
import { BusinessImplication } from "../components/BusinessImplication";
import { Card } from "../components/Card";
import { useScrollSpy } from "../hooks/useScrollSpy";
import { renderMarkdown } from "../lib/markdown";
import { usePageMeta } from "../seo";

const REPO = "https://github.com/amm-ds/portfolio/tree/main/apps/agent-chat";

const ARCHITECTURE = `\`\`\`mermaid
flowchart LR
  UI["React + TypeScript chat"] -->|"POST /chat · SSE"| API["FastAPI surface"]
  API --> AGENT["pydantic-ai agent<br/>typed Answer + budgets"]
  AGENT --> TOOLS["typed tools + skills"]
  AGENT --> RAG["retrieval + memory"]
  TOOLS --> AGENT
  RAG --> AGENT
  RAG --> DB[("Postgres + pgvector<br/>or SQLite")]
  AGENT --> GATE{"consequential action?"}
  GATE -->|"approval required"| HUMAN["approve / deny<br/>timeout = deny"]
  GATE -->|"safe output"| OUT["typed SSE response"]
  HUMAN --> OUT
\`\`\``;

const APPROVAL_FLOW = `\`\`\`mermaid
flowchart LR
  TOOL["send_message tool"] --> REQ["approval_request<br/>on the run's SSE stream"]
  REQ --> WAIT{"operator decision"}
  WAIT -->|"approve"| SEND["message sent<br/>result recorded"]
  WAIT -->|"deny or 120 s timeout"| STOP["default-deny<br/>no side effect"]
  SEND --> OUT["structured Answer"]
  STOP --> OUT
\`\`\``;

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
export AGENT_CHAT_PROVIDER=hosted
export AGENT_CHAT_HOSTED_BASE_URL=https://api.example.com/v1
export AGENT_CHAT_HOSTED_API_KEY=<secret>
export AGENT_CHAT_HOSTED_MODEL=<model>
# No agent, tool, API, or UI changes are required.
\`\`\``;

const SSE_SNIPPET = `\`\`\`json
{"type":"approval_request","approval_id":"ap_42","tool":"send_message","summary":"Weekly report"}
{"type":"approval_response","approval_id":"ap_42","approved":true}
{"type":"done","answer":{"text":"…","citations":[],"uncertainty":"low"},"usage":{"input_tokens":842,"output_tokens":117,"requests":3},"conversation_id":"conv_7"}
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
    text: "Five ADRs covering the agent, approval, memory, retrieval, and frontend choices and their limits.",
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

function ArticleSection({
  id,
  index,
  subtitle,
  takeaway,
  children,
}: {
  id: string;
  index: number;
  subtitle: string;
  takeaway: string;
  children: ReactNode;
}) {
  return (
    <section id={id} className="story-section">
      <h2>
        <span className="sec-num">{String(index).padStart(2, "0")}</span>
        {SECTIONS[index - 1].title}
      </h2>
      <p className="section-subtitle">{subtitle}</p>
      <div className="story-main">
        {children}
        <BusinessImplication label="In plain terms">{takeaway}</BusinessImplication>
      </div>
    </section>
  );
}

function Screenshot({ name, alt, caption }: { name: string; alt: string; caption: string }) {
  return (
    <figure className="app-screenshot">
      <a href={`/apps/${name}`} target="_blank" rel="noopener noreferrer" aria-label={`Open full image: ${alt}`}>
        <img src={`/apps/${name}`} alt={alt} loading="lazy" />
      </a>
      <figcaption>{caption}</figcaption>
    </figure>
  );
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
        <p className="domain">Agentic AI · FastAPI · Postgres + pgvector · React + TypeScript</p>
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
            takeaway="Start with a working application, then replace the domain pieces instead of rebuilding agent infrastructure."
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
            </div>
          </ArticleSection>

          <ArticleSection
            id="objectives"
            index={2}
            subtitle="typed tools, bounded runs, and explicit side effects"
            takeaway="The model can propose an action, but the application decides what is allowed and when a human must approve it."
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
            </div>
          </ArticleSection>

          <ArticleSection
            id="architecture"
            index={3}
            subtitle="provider, retrieval, memory, and approval boundaries stay independent"
            takeaway="Change the model, database, or domain without rewriting the application."
          >
            {renderMarkdown(ARCHITECTURE)}
            <div className="prose">
              <p>
                Retrieval returns source-addressed passages. The model sees only relevant tools
                and deferred skill descriptions, then produces the structured output. Provider
                selection lives in one factory and supports local Ollama, hosted OpenAI-compatible
                APIs, and optional fallback chains.
              </p>
            </div>
            {renderMarkdown(PROVIDER_SNIPPET)}
            {renderMarkdown(APPROVAL_FLOW)}
          </ArticleSection>

          <ArticleSection
            id="interface"
            index={4}
            subtitle="streamed answers, visible tool work, and an operator decision in-band"
            takeaway="Users can see what the agent did, what evidence it used, and where it is waiting for a decision."
          >
            <div className="app-media-grid">
              <Screenshot
                name="agent-chat-ui.png"
                alt="Agent chat interface with conversation sidebar, streamed response, tool calls and citations"
                caption="Streamed answer, tool calls, and citations in the main workspace."
              />
              <Screenshot
                name="agent-chat-approval.png"
                alt="Agent chat waiting for an operator to approve or deny a send_message action"
                caption="The run pauses for an explicit approve/deny decision."
              />
            </div>
            <div className="app-video">
              <video controls preload="metadata" playsInline poster="/apps/agent-chat-ui.png">
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
              </div>
            </div>
            {renderMarkdown(SSE_SNIPPET)}
          </ArticleSection>

          <ArticleSection
            id="memory"
            index={5}
            subtitle="durable facts without turning every prompt into a transcript"
            takeaway="Remember useful facts while keeping model context bounded and inspectable."
          >
            <div className="prose">
              <p>
                Three boundaries have separate responsibilities: conversations persist the bounded
                run, per-user notebooks store durable facts on demand, and history processing trims
                or summarizes only overflow. Postgres is primary; SQLite supports local development.
              </p>
              <p>
                Recall ranks selected notes and returns at most five by default, hard-bounded at ten.
                There is no whole-notebook injection. Recalled text remains untrusted user content,
                not a secret store or authorization boundary.
              </p>
            </div>
            <div className="app-media-grid app-media-grid--single">
              <Screenshot
                name="agent-chat-memory.png"
                alt="Agent chat memory view showing a user notebook with durable facts"
                caption="Durable facts load on demand rather than filling every prompt."
              />
            </div>
          </ArticleSection>

          <ArticleSection
            id="evaluation"
            index={6}
            subtitle="deterministic graders offline, the same suite against a real provider"
            takeaway="CI proves tool choice, grounding, refusal, and approval behavior without paying for an LLM judge."
          >
            <div className="prose">
              <p>
                A 13-case suite uses scripted fake models for deterministic CI. Exact tool-set
                assertions replace subjective judging; refusal probes cover prompt leaks,
                unsupported requests, and financial actions. A separate fact is written in one
                run and recalled in a fresh run.
              </p>
            </div>
            {renderMarkdown(EVAL_SNIPPET)}
            <div className="prose">
              <p>
                The real-model path runs the same cases and graders against the configured provider.
                The runner writes a Markdown report with per-case verdicts and total assertions.
              </p>
              <p>
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
            takeaway="The template includes the instructions needed to run, extend, and operate it after handover."
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
          </ArticleSection>

          <ArticleSection
            id="adapt"
            index={8}
            subtitle="change identity, capabilities, and infrastructure in that order"
            takeaway="Most adaptations start with instructions and a folder, not a framework migration."
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
