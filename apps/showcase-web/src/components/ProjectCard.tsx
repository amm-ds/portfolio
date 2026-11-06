import { Link } from "react-router-dom";
import type { Project, ProjectHeadline } from "../api";
import { cardAchieves, cardDoes, cardTags } from "../lib/cardCopy";
import { formatMetricValue } from "../lib/delta";
import { StudyCard } from "./StudyCard";

/** Headline selected by the compact index endpoint; absent metrics stay hidden. */
function CardKeyNumber({ headline }: { headline?: ProjectHeadline }) {
  if (!headline) return null;
  return (
    <span className="chip study-result-chip">
      {headline.metric}: {formatMetricValue(headline.value)}
    </span>
  );
}

/** Experiment card on the projects index: the shared study-card layout fed
 * from the rewritten does/achieves copy (CARD_DOES + CARD_ACHIEVES) under the
 * literal "description" / "results" block labels and exactly four short
 * technique tags (CARD_TAGS), plus the headline metric as the results chip
 * when the compact headlines index serves one. */
export function ProjectCard({
  project,
  headline,
}: {
  project: Project;
  headline?: ProjectHeadline;
}) {
  const meta = [
    { label: "topics", value: project.domain },
    ...(project.data ? [{ label: "data", value: project.data }] : []),
  ];
  return (
    <Link to={`/projects/${project.id}`} className="project-card study-card">
      <StudyCard
        title={project.title}
        meta={meta}
        doesLabel="description"
        does={cardDoes(project.id)}
        achievesLabel="results"
        achieves={cardAchieves(project.id)}
        result={<CardKeyNumber headline={headline} />}
        tags={cardTags(project.id, project.techniques)}
      />
    </Link>
  );
}
