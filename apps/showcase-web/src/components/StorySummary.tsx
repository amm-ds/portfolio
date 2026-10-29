/** Compact result, data and limitations summary for a case study. */
export function StorySummary({
  headline,
  dataNote,
  limits,
}: {
  headline?: string | null;
  dataNote?: string | null;
  limits?: string | null;
}) {
  if (!headline && !dataNote && !limits) return null;

  return (
    <section className="story-summary" aria-label="Case study summary">
      {headline && <p className="story-summary-headline">{headline}</p>}
      {(dataNote || limits) && (
        <dl className="story-summary-notes">
          {dataNote && (
            <div>
              <dt>data</dt>
              <dd>{dataNote}</dd>
            </div>
          )}
          {limits && (
            <div>
              <dt>limits</dt>
              <dd>{limits}</dd>
            </div>
          )}
        </dl>
      )}
    </section>
  );
}
