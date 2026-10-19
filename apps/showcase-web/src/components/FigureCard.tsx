import { PlotlyFigure } from "./PlotlyFigure";

/**
 * Generic figure card: a chart (native plotly, iframe fallback inside
 * PlotlyFigure) with a commentary footer below it — a small mono id line
 * (`fig :: {name}`) plus an optional caption paragraph from the story's
 * `figure_captions`. Usable by any page/project; when no caption exists yet
 * the footer falls back to the id line alone.
 */
export function FigureCard({
  pid,
  name,
  caption,
}: {
  pid: string;
  name: string;
  caption?: string;
}) {
  return (
    <div className="figure-card">
      <PlotlyFigure pid={pid} name={name} />
      <footer className="figure-card-footer">
        <span className="figure-id">fig :: {name}</span>
        {caption && <p className="figure-comment">{caption}</p>}
      </footer>
    </div>
  );
}
