import { Card } from "../components/Card";
import { PageIndex } from "../components/PageIndex";
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

const SPECS = [
  {
    title: "architecture",
    text: "Component boundaries, request lifecycle, provider/store protocols, and deployment topology.",
    href: `${REPO}/specs/architecture.md`,
  },
  {
    title: "operations",
    text: "Setup, configuration, health checks, failure modes, and the commands needed to operate the stack.",
    href: `${REPO}/specs/operations.md`,
  },
  {
    title: "adapting",
    text: "Concrete swap points for providers, tools, skills, retrieval, storage, UI styling, and deployment.",
    href: `${REPO}/specs/adapting.md`,
  },
  {
    title: "decision records",
    text: "Five ADRs explaining the agent, approval, memory, retrieval, and frontend choices and their limits.",
    href: `${REPO}/specs/decisions`,
  },
];

function Screenshot({ name, alt, caption }: { name: string; alt: string; caption: string }) {
  return (
    <figure className="app-screenshot">
      <img src={`/apps/${name}`} alt={alt} loading="lazy" />
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

  return (
    <>
      <section className="services-hero">
        <p className="kicker">&gt; apps / agent-chat</p>
        <h1>Chatbot agent — production template</h1>
        <p>
          A modular agent you can lift out and adapt: typed tools and toolsets, disk-loaded
          skills, pgvector retrieval, durable memory, human approval for consequential actions,
          and a streaming chat UI.
        </p>
        <p>
          <a href={REPO} target="_blank" rel="noopener noreferrer">source on GitHub</a>
          {" · "}
          <a href={`${REPO}/specs`} target="_blank" rel="noopener noreferrer">downloadable specs</a>
        </p>
      </section>
      <PageIndex
        items={[
          { id: "overview", label: "overview" },
          { id: "architecture", label: "architecture" },
          { id: "approval", label: "human approval" },
          { id: "interface", label: "interface" },
          { id: "memory", label: "memory" },
          { id: "evaluation", label: "evaluation" },
          { id: "specs", label: "specs" },
          { id: "adapt", label: "adapt & limits" },
        ]}
      />

      <section id="overview" className="story-section">
        <h2 className="section-title">overview</h2>
        <div className="prose">
          <p>
            The template is the chassis under a customer assistant, internal copilot, or
            policy-aware helpdesk. It keeps provider, storage, retrieval, and approval choices
            behind explicit protocols so the domain can change without rewriting the application.
          </p>
          <ul>
            <li>One <code>build_agent</code> assembly point with structured output and usage budgets.</li>
            <li>Typed toolsets and deferred skills loaded from folders.</li>
            <li>FastAPI streaming, request IDs, structured errors, and health/readiness endpoints.</li>
            <li>React conversation UI with tool traces, citations, and approval cards.</li>
          </ul>
        </div>
      </section>

      <section id="architecture" className="story-section">
        <h2 className="section-title">architecture & pipeline</h2>
        <p className="section-intro">
          Provider, tools, retrieval, memory, and approval boundaries stay independent of the domain.
        </p>
        {renderMarkdown(ARCHITECTURE)}
        <div className="prose">
          <p>
            The model sees only the tools and skill descriptions it needs. Retrieval returns
            source-addressed passages; the final <code>Answer</code> carries text, citations, and
            self-reported uncertainty. Every run is bounded by request and token budgets.
          </p>
        </div>
      </section>

      <section id="approval" className="story-section">
        <h2 className="section-title">human approval</h2>
        <p className="section-intro">
          Consequential tools pause their own run; other conversations continue independently.
        </p>
        {renderMarkdown(APPROVAL_FLOW)}
        <div className="prose">
          <p>
            The approval decision uses the same SSE stream as the answer. A lost connection or a
            120-second wait defaults to denial. Tests can substitute auto-approval or deny-all
            implementations without changing the agent contract.
          </p>
        </div>
        <Screenshot
          name="agent-chat-approval.png"
          alt="Agent chat waiting for an operator to approve or deny a send_message action"
          caption="The run waits on an explicit decision; no side effect occurs by default."
        />
      </section>

      <section id="interface" className="story-section">
        <h2 className="section-title">interface</h2>
        <p className="section-intro">
          The UI exposes the work: streamed deltas, tool calls, citations, and conversation state.
        </p>
        <Screenshot
          name="agent-chat-ui.png"
          alt="Agent chat interface with conversation sidebar, streamed response, tool calls and citations"
          caption="A complete React + TypeScript surface, styled through one block of CSS variables."
        />
      </section>

      <section id="memory" className="story-section">
        <h2 className="section-title">memory</h2>
        <div className="prose">
          <p>
            Three boundaries prevent memory from becoming an unbounded prompt: persisted
            conversations, per-user notebooks loaded on demand, and bounded model history with
            optional summarization. Postgres is primary; SQLite supports local development.
          </p>
        </div>
        <Screenshot
          name="agent-chat-memory.png"
          alt="Agent chat memory view showing a user notebook with durable facts"
          caption="Durable facts stay available without injecting the whole notebook into every prompt."
        />
      </section>

      <section id="evaluation" className="story-section">
        <h2 className="section-title">evaluation</h2>
        <div className="prose">
          <p>
            A 13-case offline suite grades tool choice, grounding, refusal behavior, and approval
            outcomes with deterministic graders. Scripted fake models make CI independent of
            network access and API keys; the same runner can evaluate a real deployment.
          </p>
          <ul>
            <li>Exact tool-set assertions rather than an LLM judge.</li>
            <li>Citation checks for retrieval-backed answers.</li>
            <li>Refusal probes for prompt leaks, unsupported requests, and financial actions.</li>
            <li>A Markdown report generated by <code>agent_chat.evals.runner.write_report</code>.</li>
          </ul>
          <p>
            <a href={`${REPO}/src/agent_chat/evals`} target="_blank" rel="noopener noreferrer">
              eval cases and deterministic graders →
            </a>
          </p>
        </div>
      </section>

      <section id="specs" className="story-section">
        <h2 className="section-title">specs & downloads</h2>
        <div className="app-spec-grid">
          {SPECS.map((spec) => (
            <Card key={spec.title} className="app-spec-card">
              <h3>{spec.title}</h3>
              <p>{spec.text}</p>
              <a href={spec.href} target="_blank" rel="noopener noreferrer">open spec →</a>
            </Card>
          ))}
        </div>
      </section>

      <section id="adapt" className="story-section">
        <h2 className="section-title">adapt & limits</h2>
        <div className="prose">
          <ul>
            <li><strong>Identity:</strong> edit <code>BASE_INSTRUCTIONS</code> in <code>agent.py</code>, preserving tool discipline and escalation rules.</li>
            <li><strong>Capability:</strong> register a typed tool or add a skill folder; no agent rewrite.</li>
            <li><strong>Infrastructure:</strong> swap provider, embedder, vector store, or database behind the documented protocols.</li>
          </ul>
          <p>
            <strong>Limits:</strong> this is a single-agent chassis, not multi-agent orchestration.
            It does not ship your domain corpus, credentials, production SLOs, or a free-hosted LLM.
            Those choices belong to the adopter and are explicit in the operations guide.
          </p>
          <p>
            <a href={`${REPO}/README.md`} target="_blank" rel="noopener noreferrer">
              start with the app README →
            </a>
          </p>
        </div>
      </section>
    </>
  );
}
