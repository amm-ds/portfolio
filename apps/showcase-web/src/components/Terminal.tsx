import type { ReactNode } from "react";

/** Terminal window chrome: traffic-light dots + title bar around content. */
export function Terminal({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="terminal">
      <div className="terminal-titlebar">
        <span className="terminal-dots" aria-hidden="true">
          <span />
          <span />
          <span />
        </span>
        <span>{title}</span>
      </div>
      <div className="terminal-body">{children}</div>
    </div>
  );
}
