import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getMetrics, type Project } from "../api";
import { impactLine } from "../lib/impact";
import { formatMetricValue, pickHeadlineMetric } from "../lib/delta";

/** Live headline metric for a card: first non-baseline run's first metric; hidden until loaded. */
function CardKeyNumber({ projectId }: { projectId: string }) {
  const [text, setText] = useState<string | null>(null);
  useEffect(() => {
    let cancelled = false;
    getMetrics(projectId)
      .then((m) => {
        if (cancelled || !m) return;
        const h = pickHeadlineMetric(m);
        if (h) setText(`${h.metric}: ${formatMetricValue(h.value)}`);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [projectId]);
  if (!text) return null;
  return <span className="key-number">{text}</span>;
}

export function ProjectCard({ project }: { project: Project }) {
  const impact = impactLine(project.id);
  return (
    <Link to={`/projects/${project.id}`} className="project-card">
      <div className="project-card-top">
        <div>
          <h3>{project.title}</h3>
          <p className="domain">{project.domain}</p>
        </div>
      </div>
      {impact && <p className="impact">{impact}</p>}
      <div className="chips">
        {project.techniques.map((t) => (
          <span key={t} className="chip">
            {t}
          </span>
        ))}
      </div>
      <p className="data">
        <strong>Data:</strong> {project.data} <CardKeyNumber projectId={project.id} />
      </p>
    </Link>
  );
}
