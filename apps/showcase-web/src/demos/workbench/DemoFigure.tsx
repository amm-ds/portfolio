import type { ReactNode } from "react";

/** Shared demo figure chrome: visualization content plus a commentary band. */
export function DemoFigure({ comment, children }: { comment: ReactNode; children: ReactNode }) {
  return (
    <div className="figure-card">
      {children}
      <footer className="figure-card-band">
        <p className="figure-comment">{comment}</p>
      </footer>
    </div>
  );
}
