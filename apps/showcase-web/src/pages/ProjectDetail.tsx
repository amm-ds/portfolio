import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
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
import { FigureFrame } from "../components/FigureFrame";
import { MetricsTable } from "../components/MetricsTable";
import { REPO_URL } from "../config";
import { summaryLine } from "../lib/impact";
import { usePageMeta } from "../seo";

/** Generic demo line, used only when neither the manifest nor the registry
 * description is reachable. */
const GENERIC_DEMO_LINE =
  "an interactive session over this project's committed payloads — change the inputs and watch the measured outputs respond.";

/** "01-rag-agent" → https://amm-ds.github.io/portfolio/projects/01-rag-agent/ */
function docsUrl(projectId: string): string {
  const [num, ...slug] = projectId.split("-");
  return `https://amm-ds.github.io/portfolio/projects/${num}-${slug.join("-")}/`;
}

interface Detail {
  title: string;
  domain: string;
  techniques: string[];
}

// --- Evaluation-report probe ---------------------------------------------------
// The API serves the full HTML report at /projects/{id}/report and 404s when the
// pipeline has not produced one. Probe once per id (module-level cache, promise
// deduped) and show the link only when it would 200. GET rather than HEAD: the
// FastAPI route answers GET only; the body is never consumed.
const reportProbeCache = new Map<string, Promise<boolean>>();

function hasReport(projectId: string): Promise<boolean> {
  let probe = reportProbeCache.get(projectId);
  if (!probe) {
    probe = fetch(`/projects/${projectId}/report`)
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
  const [storyLoading, setStoryLoading] = useState(true);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [figures, setFigures] = useState<string[]>([]);
  const [demoHref, setDemoHref] = useState<string | null>(null);
  const [demoLine, setDemoLine] = useState<string | null>(null);
  const [reportOk, setReportOk] = useState(false);

  usePageMeta({
    title: detail?.title ?? "Unknown project",
    description:
      summaryLine(id) ?? "An experiment from the amm-ds ML/AI engineering portfolio.",
    noindex: notFound || undefined,
  });

  // Live-demo CTA + banner: match this project against the demo registry
  // (fetched once per mount). The banner description prefers the demo
  // manifest, falls back to the registry hook, then to a generic line.
  useEffect(() => {
    let cancelled = false;
    setDemoHref(null);
    setDemoLine(null);
    getDemoRegistry()
      .then(async (entries) => {
        const entry = entries.find((e) => e.project === id);
        if (!entry) return;
        if (!cancelled) setDemoHref(entry.href);
        try {
          const manifest = await getDemoManifest(entry.id);
          if (!cancelled) setDemoLine(manifest.hook || GENERIC_DEMO_LINE);
        } catch {
          if (!cancelled) setDemoLine(entry.hook || GENERIC_DEMO_LINE);
        }
      })
      .catch(() => {
        if (cancelled) return;
        setDemoHref(null);
        setDemoLine(null);
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

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
    setStoryLoading(true);
    setMetrics(null);
    setFigures([]);
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
        setStoryLoading(false);
      })
      .catch(() => {
        if (cancelled) return;
        setStory(null);
        setStoryLoading(false);
      });

    getMetrics(id)
      .then((m) => !cancelled && setMetrics(m))
      .catch(() => !cancelled && setMetrics(null));

    return () => {
      cancelled = true;
    };
  }, [id]);

  // Figures list only feeds the raw-artifacts fallback (stories reference figures directly).
  useEffect(() => {
    if (storyLoading || story !== null) return;
    let cancelled = false;
    getFigures(id)
      .then((f) => !cancelled && setFigures(f))
      .catch(() => !cancelled && setFigures([]));
    return () => {
      cancelled = true;
    };
  }, [id, story, storyLoading]);

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

  return (
    <>
      <ExperimentCrumbs projectId={id} projects={projects} />
      {error && <div className="state-box error">{error}</div>}
      {detail === null && !error ? (
        <p className="loading">loading project…</p>
      ) : detail ? (
        <header className="detail-header">
          <h1>{detail.title}</h1>
          {story?.short_version && <p className="detail-lead">{story.short_version}</p>}
          <p className="domain">{detail.domain}</p>
          <div className="chips">
            {detail.techniques.map((t) => (
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
              <a
                className="chip-link"
                href={`/projects/${id}/report`}
                target="_blank"
                rel="noreferrer"
              >
                [full evaluation report]
              </a>
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
            <p className="demo-banner-line">{demoLine ?? GENERIC_DEMO_LINE}</p>
          </div>
          <Link className="demo-banner-cta" to={demoHref}>
            ▶ try the live demo
          </Link>
        </aside>
      )}

      {storyLoading ? (
        <p className="loading">loading case study…</p>
      ) : story ? (
        <CaseStudy projectId={id} story={story} metrics={metrics} />
      ) : (
        <>
          <h2 className="section-title">metrics</h2>
          {metrics === null ? (
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
          {figures.length === 0 ? (
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
                <FigureFrame key={name} projectId={id} name={name} />
              ))}
            </div>
          )}
        </>
      )}

      <ExperimentNav projectId={id} projects={projects} />
    </>
  );
}
