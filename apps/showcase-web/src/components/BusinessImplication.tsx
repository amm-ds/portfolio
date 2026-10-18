import type { ReactNode } from "react";

/** Distinct card for a section's trailing `**Business summary:**` paragraph. */
export function BusinessImplication({ children }: { children: ReactNode }) {
  return (
    <aside className="bi-card" aria-label="Business summary">
      <p className="bi-label">Business summary</p>
      <div className="bi-body">{children}</div>
    </aside>
  );
}
