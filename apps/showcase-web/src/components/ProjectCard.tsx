import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getMetrics, type Project } from "../api";
import { cardAchieves, cardDoes, cardTags } from "../lib/cardCopy";
import { formatMetricValue, pickHeadlineMetric } from "../lib/delta";
import { StudyCard } from "./StudyCard";

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

/** Experiment card on the projects index: the shared study-card layout fed
 * from the rewritten does/achieves copy (CARD_DOES + CARD_ACHIEVES) and
 * exactly four short technique tags (CARD_TAGS), plus the live headline
 * metric as the brief result when the registry serves one (data). */
export function ProjectCard({ project }: { project: Project }) {
  const subtitle = project.data ? `${project.domain} · ${project.data}` : project.domain;
  return (
    <Link to={`/projects/${project.id}`} className="project-card study-card">
      <StudyCard
        title={project.title}
        subtitle={subtitle}
        does={cardDoes(project.id)}
        achieves={cardAchieves(project.id)}
        result={<CardKeyNumber projectId={project.id} />}
        tags={cardTags(project.id, project.techniques)}
      />
    </Link>
  );
}
