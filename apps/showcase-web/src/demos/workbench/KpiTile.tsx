export type KpiTone = "good" | "bad" | "neutral";

/** Headline number tile for the workbench insight rail. */
export function KpiTile({
  label,
  value,
  sub,
  tone = "neutral",
}: {
  label: string;
  value: string;
  sub?: string;
  tone?: KpiTone;
}) {
  return (
    <div className={`wb-kpi wb-kpi-${tone}`}>
      <span className="wb-kpi-label">{label}</span>
      <span className="wb-kpi-value">{value}</span>
      {sub !== undefined && <span className="wb-kpi-sub">{sub}</span>}
    </div>
  );
}
