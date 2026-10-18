import type { ReactNode } from "react";

/** Distinct card for a section's trailing `**Business implication:**` paragraph. */
export function BusinessImplication({ children }: { children: ReactNode }) {
  return (
    <aside className="bi-card" aria-label="Business implication">
      <p className="bi-label">Business implication</p>
      <div className="bi-body">{children}</div>
    </aside>
  );
}
