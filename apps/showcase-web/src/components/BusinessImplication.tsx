import type { ReactNode } from "react";

/** Distinct card for a section's trailing takeaway paragraph. */
export function BusinessImplication({
  children,
  label = "Business summary",
}: {
  children: ReactNode;
  label?: "Business summary" | "In plain terms";
}) {
  return (
    <aside className="bi-card" aria-label={label}>
      <p className="bi-label">{label}</p>
      <div className="bi-body">{children}</div>
    </aside>
  );
}
