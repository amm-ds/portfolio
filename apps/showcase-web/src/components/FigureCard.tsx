import { PlotlyFigure } from "./PlotlyFigure";

/**
 * Generic figure card: one bordered tile holding a chart (native plotly,
 * iframe fallback inside PlotlyFigure) on top and a commentary band at the
 * bottom — a small mono id line (`fig :: {name}`) plus an optional caption
 * paragraph from the story's `figure_captions`. Usable by any page/project;
 * when no caption exists yet the band falls back to the id line alone.
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
      <footer className="figure-card-band">
        <span className="figure-id">fig :: {name}</span>
        {caption && <p className="figure-comment">{caption}</p>}
      </footer>
    </div>
  );
}
