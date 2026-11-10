import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  ApiError,
  getDemoManifest,
  getDemoRegistry,
  getFigures,
  getMetrics,
  getProjects,
  getStory,
  type Metrics,
  type Project,
  type ProjectStoryData,
} from "../api";
import { CaseStudy } from "../components/CaseStudy";
import { ExperimentCrumbs, ExperimentNav } from "../components/ExperimentNav";
import { MetricsTable } from "../components/MetricsTable";
import { PlotlyFigure } from "../components/PlotlyFigure";
import { DOCS_URL, REPO_URL } from "../config";
import { DEMOS } from "../lib/demos";
import { STATIC_PROJECTS } from "../lib/staticRegistry";
import { summaryLine } from "../lib/impact";
import { usePageMeta } from "../seo";

/** Generic demo line, used only when neither the manifest nor the registry
 * description is reachable. */
const GENERIC_DEMO_LINE =
  "an interactive session over this project's committed payloads — change the inputs and watch the measured outputs respond.";

/** "01-rag-agent" → <DOCS_URL>/projects/01-rag-agent/ — the docs base comes from
 * the DOCS_URL/VITE_DOCS_URL override (see config.ts), never a hardcoded domain. */
function docsUrl(projectId: string): string {
  const [num, ...slug] = projectId.split("-");
  return `${DOCS_URL}/projects/${num}-${slug.join("-")}/`;
}

interface Detail {
  title: string;
  domain: string;
  techniques: string[];
}

/** Header fields from the baked static registry — first paint renders without
 * waiting on the API detail (the audit's client-fetch LCP waterfall); the
 * fetched detail replaces these with identical values once loaded. */
function bakedDetailFor(id: string): Detail | null {
  const card = STATIC_PROJECTS.find((p) => p.id === id);
  if (!card) return null;
  return { title: card.title, domain: card.domain, techniques: card.techniques };
}

// --- Evaluation-report probe ---------------------------------------------------
// The API serves the full HTML report at /projects/{id}/report and 404s when the
// pipeline has not produced one. Probe availability with a bodyless HEAD once
// per id (module-level cache, promise deduped); GET remains for the report page.
const reportProbeCache = new Map<string, Promise<boolean>>();

function hasReport(projectId: string): Promise<boolean> {
  let probe = reportProbeCache.get(projectId);
  if (!probe) {
    probe = fetch(`/projects/${projectId}/report`, { method: "HEAD" })
      .then((res) => res.ok)
      .catch(() => false);
    reportProbeCache.set(projectId, probe);
  }
  return probe;
}

export function ProjectDetail() {
  const { id = "" } = useParams();
  const [projects, setProjects] = useState<Project[]>([]);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [story, setStory] = useState<ProjectStoryData | null>(null);
  const [storyStatus, setStoryStatus] = useState<"loading" | "ready" | "missing" | "error">(
    "loading",
  );
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [metricsStatus, setMetricsStatus] = useState<"loading" | "ready" | "missing" | "error">(
    "loading",
  );
  const [figures, setFigures] = useState<string[] | null>(null);
  const [figuresStatus, setFiguresStatus] = useState<"loading" | "ready" | "error">("loading");
  // Live-demo banner: the link and placeholder line come from the baked
  // static registry, so the banner renders with the header on first paint —
  // popping it in after the registry fetch was the audit's 0.62 CLS shift.
  // The manifest/registry fetch below refines the same values (production
  // resolves to identical strings, so nothing moves; tests and stale bakes
  // still get the live answer).
  const bakedDemo = useMemo(() => DEMOS.find((d) => d.project === id) ?? null, [id]);
  const bakedDetail = useMemo(() => bakedDetailFor(id), [id]);
  const headerDetail = detail ?? bakedDetail;
  const [liveDemo, setLiveDemo] = useState<{ href: string; line: string } | null>(null);
  const [reportOk, setReportOk] = useState(false);
  const [attempt, setAttempt] = useState(0);

  usePageMeta({
    title: detail?.title ?? "Unknown project",
    description:
      summaryLine(id) ?? "An experiment from the alejandromerida.dev ML/AI engineering portfolio.",
    noindex: notFound || undefined,
  });

  // Manifest description: prefer the demo manifest's hook, fall back to the
  // live registry entry's hook; the baked line above stays otherwise.
  useEffect(() => {
    let cancelled = false;
    setLiveDemo(null);
    getDemoRegistry()
      .then(async (entries) => {
        const entry = entries.find((e) => e.project === id);
        if (!entry) return;
        let line = entry.hook || GENERIC_DEMO_LINE;
        try {
          const manifest = await getDemoManifest(entry.id);
          line = manifest.hook || line;
        } catch {
          /* registry hook stays */
        }
        if (!cancelled) setLiveDemo({ href: entry.href, line });
      })
      .catch(() => {
        /* baked values remain */
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  const demoHref = liveDemo?.href ?? bakedDemo?.href ?? null;
  const demoLine = liveDemo?.line ?? bakedDemo?.line ?? GENERIC_DEMO_LINE;

  // Evaluation report link: probe once per id (cached module-level).
  useEffect(() => {
    let cancelled = false;
    setReportOk(false);
    hasReport(id)
      .then((ok) => !cancelled && setReportOk(ok))
      .catch(() => !cancelled && setReportOk(false));
    return () => {
      cancelled = true;
    };
  }, [id]);

  useEffect(() => {
    let cancelled = false;
    setProjects([]);
    setDetail(null);
    setNotFound(false);
    setStory(null);
    setStoryStatus("loading");
    setMetrics(null);
    setMetricsStatus("loading");
    setFigures(null);
    setFiguresStatus("loading");
    setError(null);

    getProjects()
      .then((list) => {
        if (cancelled) return;
        setProjects(list);
        const project = list.find((p) => p.id === id);
        if (!project) {
          setNotFound(true);
          return;
        }
        setDetail({
          title: project.title,
          domain: project.domain,
          techniques: project.techniques,
        });
      })
      .catch(() => !cancelled && setError("could not load project metadata from the API."));

    getStory(id)
      .then((s) => {
        if (cancelled) return;
        setStory(s);
        setStoryStatus(s === null ? "missing" : "ready");
      })
      .catch(() => {
        if (cancelled) return;
        setStory(null);
        setStoryStatus("error");
      });

    getMetrics(id)
      .then((m) => {
        if (cancelled) return;
        setMetrics(m);
        setMetricsStatus(m === null ? "missing" : "ready");
      })
      .catch(() => !cancelled && setMetricsStatus("error"));

    return () => {
      cancelled = true;
    };
  }, [id, attempt]);

  // Figures list only feeds the raw-artifacts fallback (stories reference figures directly).
  useEffect(() => {
    if (storyStatus !== "missing") return;
    let cancelled = false;
    setFiguresStatus("loading");
    getFigures(id)
      .then((f) => {
        if (cancelled) return;
        setFigures(f);
        setFiguresStatus("ready");
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        if (e instanceof ApiError && e.status === 404) {
          setFigures([]);
          setFiguresStatus("ready");
        } else {
          setFiguresStatus("error");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [id, storyStatus]);

  if (notFound) {
    return (
      <div className="state-box">
        <h1>Unknown project</h1>
        <p>
          I couldn't find an experiment called <code>{id}</code>. It may have been
          renamed or retired — browse the current experiments instead.
        </p>
        <p>
          <Link to="/projects">← all experiments</Link>
        </p>
      </div>
    );
  }

  const retryButton = (
    <button type="button" onClick={() => setAttempt((n) => n + 1)}>
      Retry
    </button>
  );

  if (error) {
    return (
      <div className="state-box error" role="alert">
        <h1>Project could not be loaded</h1>
        <p>{error}</p>
        <p>
          {retryButton} <Link to="/projects">← all experiments</Link>
        </p>
      </div>
    );
  }

  return (
    <>
      <ExperimentCrumbs projectId={id} projects={projects} />
      {detail === null && bakedDetail === null ? (
        <p className="loading">loading project…</p>
      ) : headerDetail ? (
        <header className="detail-header">
          <h1>{headerDetail.title}</h1>
          {(story?.short_version ?? summaryLine(id)) && (
            <p className="detail-lead">{story?.short_version ?? summaryLine(id)}</p>
          )}
          <p className="domain">{headerDetail.domain}</p>
          <div className="chips">
            {headerDetail.techniques.map((t) => (
              <span key={t} className="chip">
                {t}
              </span>
            ))}
          </div>
          <div className="meta-links">
            {demoHref && (
              <Link className="chip-link demo-cta" to={demoHref}>
                ▶ try the live demo
              </Link>
            )}
            <a
              className="chip-link"
              href={`${REPO_URL}/tree/main/projects/${id}`}
              target="_blank"
              rel="noreferrer"
            >
              [code]
            </a>
            <a className="chip-link" href={docsUrl(id)} target="_blank" rel="noreferrer">
              [docs]
            </a>
            {reportOk && (
              <Link className="chip-link" to={`/projects/${id}/report`}>
                [full evaluation report]
              </Link>
            )}
            <a className="chip-link" href={REPO_URL} target="_blank" rel="noreferrer">
              [repo]
            </a>
          </div>
        </header>
      ) : null}

      {demoHref && (
        <aside className="demo-banner accent-card" aria-label="Live demo">
          <div>
            <p className="demo-banner-label">live demo</p>
            <p className="demo-banner-line">{demoLine}</p>
          </div>
          <Link className="demo-banner-cta" to={demoHref}>
            ▶ try the live demo
          </Link>
        </aside>
      )}

      {storyStatus === "loading" ? (
        <p className="loading">loading case study…</p>
      ) : storyStatus === "error" ? (
        <div className="state-box error" role="alert">
          The case study could not be loaded. {retryButton}
        </div>
      ) : storyStatus === "ready" && story ? (
        <>
          {metricsStatus === "error" && (
            <div className="state-box error" role="alert">
              Metrics could not be loaded. {retryButton}
            </div>
          )}
          <CaseStudy projectId={id} story={story} metrics={metrics} />
        </>
      ) : (
        <>
          <h2 className="section-title">metrics</h2>
          {metricsStatus === "loading" ? (
            <p className="loading">loading metrics…</p>
          ) : metricsStatus === "error" ? (
            <div className="state-box error" role="alert">
              Metrics could not be loaded. {retryButton}
            </div>
          ) : metrics === null ? (
            <div className="state-box">
              No metrics yet for this project —{" "}
              <a href={REPO_URL} target="_blank" rel="noreferrer">
                run the pipeline
              </a>{" "}
              to generate results.
            </div>
          ) : (
            <MetricsTable metrics={metrics} />
          )}

          <h2 className="section-title">figures</h2>
          {figuresStatus === "error" ? (
            <div className="state-box error" role="alert">
              Figures could not be loaded. {retryButton}
            </div>
          ) : figuresStatus === "loading" || figures === null ? (
            <p className="loading">loading figures…</p>
          ) : figures.length === 0 ? (
            <div className="state-box">
              No figures yet for this project —{" "}
              <a href={REPO_URL} target="_blank" rel="noreferrer">
                run the pipeline
              </a>{" "}
              to generate results.
            </div>
          ) : (
            <div className="figure-list">
              {figures.map((name) => (
                <PlotlyFigure key={name} pid={id} name={name} caption={`fig :: ${name}`} />
              ))}
            </div>
          )}
        </>
      )}

      <ExperimentNav projectId={id} projects={projects} />
    </>
  );
}
