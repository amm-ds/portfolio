import { figureUrl } from "../api";

/** A single project figure embedded as a full HTML page in a responsive iframe. */
export function FigureFrame({ projectId, name }: { projectId: string; name: string }) {
  return (
    <figure className="figure-frame">
      <h3>{name}</h3>
      <div className="frame-wrap">
        <iframe
          src={figureUrl(projectId, name)}
          title={`Figure: ${name}`}
          loading="lazy"
        />
      </div>
    </figure>
  );
}
