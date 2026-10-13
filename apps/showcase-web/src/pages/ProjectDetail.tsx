import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  getFigures,
  getMetrics,
  getProjects,
  getStory,
  type Metrics,
  type ProjectStoryData,
} from "../api";
import { CaseStudy } from "../components/CaseStudy";
import { FigureFrame } from "../components/FigureFrame";
import { MetricsTable } from "../components/MetricsTable";

const REPO_URL = "https://github.com/amm-ds/portfolio";

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

export function ProjectDetail() {
  const { id = "" } = useParams();
  const [detail, setDetail] = useState<Detail | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [story, setStory] = useState<ProjectStoryData | null>(null);
  const [storyLoading, setStoryLoading] = useState(true);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [figures, setFigures] = useState<string[]>([]);

  useEffect(() => {
    let cancelled = false;
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
        <p>
          Unknown project <code>{id}</code>. Back to the <Link to="/">project list</Link>.
        </p>
      </div>
    );
  }

  return (
    <>
      {error && <div className="state-box error">{error}</div>}
      {detail === null && !error ? (
        <p className="loading">loading project…</p>
      ) : detail ? (
        <header className="detail-header">
          <h1>{detail.title}</h1>
          <p className="domain">{detail.domain}</p>
          <div className="chips">
            {detail.techniques.map((t) => (
              <span key={t} className="chip">
                {t}
              </span>
            ))}
          </div>
          <div className="meta-links">
            <a
              href={`https://github.com/amm-ds/portfolio/tree/main/projects/${id}`}
              target="_blank"
              rel="noreferrer"
            >
              [code]
            </a>
            <a href={docsUrl(id)} target="_blank" rel="noreferrer">
              [docs]
            </a>
            <a href={REPO_URL} target="_blank" rel="noreferrer">
              [source]
            </a>
          </div>
        </header>
      ) : null}

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
    </>
  );
}
