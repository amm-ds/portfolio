import type { ReactNode } from "react";

/** One-sentence, state-aware takeaway with an accent border. */
export function Notice({ children }: { children: ReactNode }) {
  return (
    <p className="wb-notice">
      <span className="wb-notice-mark">▸</span> {children}
    </p>
  );
}
