import { AppArticleSection, AppScreenshot } from "../components/AppArticle";
import { Card } from "../components/Card";
import { LazyFlowDiagram } from "../components/diagrams/LazyFlowDiagram";
import { useScrollSpy } from "../hooks/useScrollSpy";
import { renderMarkdown } from "../lib/markdown";
import { usePageMeta } from "../seo";

const REPO = "https://github.com/amm-ds/portfolio/tree/main/apps/eval-workbench";
const SECTIONS = [
  { id: "background", title: "Background" },
  { id: "architecture", title: "Architecture" },
  { id: "evaluation", title: "Evaluation" },
  { id: "results", title: "Results" },
  { id: "conclusions", title: "Conclusions" },
] as const;

const RUN_SNIPPET = `\`\`\`bash
cd apps/eval-workbench/web
npm ci
npm run dev
# Provider-free UI preview with clearly labeled synthetic records:
VITE_MOCK=1 npm run dev
\`\`\``;

const CONTRACT_SNIPPET = `\`\`\`typescript
// Only completed runs from the selected dataset version enter a chart.
const completed = runs.filter(
  (run) => run.status === "completed" && run.metrics !== null,
);
// Wrong predictions and execution failures remain separate evidence.
\`\`\``;

const RESOURCES = [
  { title: "application source", text: "The standalone application workspace, API contracts, frontend, and case-study source.", href: REPO },
  { title: "workbench frontend", text: "Typed HTTP client, runtime validators, registry, run review, charts, and tests.", href: `${REPO}/web` },
  { title: "portfolio article", text: "The five-section case study, evidence boundaries, and adoption limits.", href: `${REPO}/story.yaml` },
];

export function EvalWorkbenchArticle() {
  usePageMeta({
    title: "Eval Workbench — model evaluation review",
    description: "Inspect versioned evaluation datasets, case-level runs, and same-dataset quality, latency, and cost trade-offs in a React workbench.",
    canonical: "/apps/eval-workbench",
  });
  const active = useScrollSpy(SECTIONS.map((section) => section.id));

  return (
    <>
      <header className="detail-header">
        <p className="kicker">&gt; apps / eval-workbench</p>
        <h1>Eval Workbench</h1>
        <p className="detail-lead">
          <strong>Dataset versions, run evidence, and model trade-offs in one read-only review surface.</strong>
          Inspect the cases behind an aggregate, then compare completed runs on the same pinned data.
        </p>
        <div className="chips" aria-label="Technology stack">
          {["Model evaluation", "FastAPI", "React + TypeScript", "accessible charts", "runtime contracts"].map((tech) => (
            <span key={tech} className="chip">{tech}</span>
          ))}
        </div>
        <div className="meta-links">
          <a className="chip-link" href={REPO} target="_blank" rel="noopener noreferrer">[source]</a>
          <a className="chip-link" href={`${REPO}/story.yaml`} target="_blank" rel="noopener noreferrer">[story]</a>
        </div>
      </header>
      <div className="story-layout">
        <nav className="rail" aria-label="App article sections">
          <span className="rail-label">index</span>
          {SECTIONS.map((section, index) => (
            <a key={section.id} href={`#${section.id}`} className={active === section.id ? "active" : ""} aria-current={active === section.id ? "location" : undefined}>
              <span className="rail-num">{String(index + 1).padStart(2, "0")}</span> {section.title.toLowerCase()}
            </a>
          ))}
        </nav>
        <div>
          <AppArticleSection id="background" index={1} title="Background" subtitle="the cases and dataset behind every score stay visible" takeaway="One review surface connects a pinned dataset, the case-level evidence, and recorded quality, latency, and cost trade-offs.">
            <div className="prose">
              <p>Evaluation results are hard to use when the dataset, run record, and comparison live in different files. Eval Workbench brings them together without letting the browser execute a model, rewrite an expected output, or invent a composite score.</p>
              <ul>
                <li>A versioned registry fixes which inputs and expected outputs a run answered.</li>
                <li>The run view exposes individual outputs, misses, execution errors, and latency.</li>
                <li>Comparison charts include completed runs from that dataset version only.</li>
              </ul>
              <p>The provider-free preview uses synthetic support-routing and refusal-probe fixtures. Those numbers demonstrate the interface; they are not live model-quality evidence.</p>
            </div>
            <AppScreenshot name="eval-workbench.png" alt="Eval Workbench showing a synthetic support-routing dataset, case-level run results, and model comparison charts" caption="Fixture mode: registry, run detail, and same-dataset comparison. All model names and values are synthetic." />
          </AppArticleSection>

          <AppArticleSection id="architecture" index={2} title="Architecture" subtitle="the API owns records; TypeScript guards the read path" takeaway="Runtime validation sits between FastAPI and every view. Selecting a dataset replaces both run history and comparison, preventing cross-version charts.">
            <LazyFlowDiagram specId="app-eval-workbench-architecture" />
            <div className="prose">
              <p>Three endpoints supply the registry, run history, and selected run's cases. Parsers reject missing fields, unsupported states, non-finite numbers, and quality scores outside 0–1 before React renders them.</p>
              <p>The charts have no plotting dependency. CSS bars support a quick scan; an adjacent table repeats every exact value. Dark and light themes, keyboard focus, a skip link, and responsive layouts ship in the same interface.</p>
            </div>
            {renderMarkdown(CONTRACT_SNIPPET)}
          </AppArticleSection>

          <AppArticleSection id="evaluation" index={3} title="Evaluation" subtitle="test the user workflow and the trust boundary, not a fabricated benchmark" takeaway="Thirteen frontend checks cover workflows, malformed responses, and HTTP behavior. Fixture values verify rendering only; no live model benchmark is claimed.">
            <div className="prose">
              <p>Mocked HTTP responses cover loading, dataset switching, case filtering, network failures, and theme controls. Contract tests reject an out-of-range score, malformed case verdict, and unsupported run state. Client tests cover path escaping and API errors.</p>
              <ul>
                <li>Accuracy and F1 use fixed 0–1 axes; higher is better.</li>
                <li>p95 latency and recorded cost use separate axes; lower is better.</li>
                <li>Each bar is one run, not an average that would hide repeat variability.</li>
                <li>No weighted overall score hides the acceptance trade-off.</li>
              </ul>
            </div>
            {renderMarkdown(RUN_SNIPPET)}
          </AppArticleSection>

          <AppArticleSection id="results" index={4} title="Results" subtitle="a working review interface, with the evidence status named" takeaway="Delivered: registry, run history, case review, and four comparison charts. The synthetic fixture comparison is not evidence about real providers.">
            <div className="prose">
              <p>The three support-routing fixtures deliberately disagree across dimensions: <code>fixture-strict</code> has the highest fixture accuracy (1.00), while <code>fixture-fast</code> has the lowest fixture p95 latency (410 ms). This makes the trade-off visible without declaring a universal winner.</p>
              <p>A reviewer can switch to the refusal-probe dataset and see its run and cases replace the previous selection. The Needs review filter isolates incorrect or failed cases; All restores the complete record. At delivery, all thirteen frontend tests, strict TypeScript compilation, ESLint, and the production build pass.</p>
            </div>
          </AppArticleSection>

          <AppArticleSection id="conclusions" index={5} title="Conclusions" subtitle="use the UI to inspect evidence, not to manufacture certainty" takeaway="The workbench makes recorded comparisons reviewable. Representative data, validated graders, uncertainty, backend integration, and access control remain adoption responsibilities.">
            <div className="prose">
              <p>A comparison starts with dataset identity. Case-level misses and execution failures need separate labels because they require different engineering responses. Exact tables belong beside visual charts because audit work needs values, not just bar lengths.</p>
              <p><strong>Limits:</strong> the frontend is read-only and its tests use mocked HTTP responses. Live provider quality, statistical uncertainty, backend integration, and production authentication are not established by these checks. An adopter still needs representative datasets, explicit acceptance thresholds, and access controls appropriate to the data.</p>
            </div>
            <div className="app-spec-grid">
              {RESOURCES.map((resource) => (
                <Card key={resource.title} className="app-spec-card">
                  <span className="study-block-label">resource</span>
                  <h3>{resource.title}</h3>
                  <p>{resource.text}</p>
                  <a href={resource.href} target="_blank" rel="noopener noreferrer">open resource →</a>
                </Card>
              ))}
            </div>
          </AppArticleSection>
        </div>
      </div>
    </>
  );
}
