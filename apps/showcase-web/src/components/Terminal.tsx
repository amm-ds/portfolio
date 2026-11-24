import type { ReactNode } from "react";

/** Terminal window chrome: title bar around content. */
export function Terminal({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="terminal">
      <div className="terminal-titlebar">
        <span>{title}</span>
      </div>
      <div className="terminal-body">{children}</div>
    </div>
  );
}
