import type { ReactNode } from "react";
import { Link } from "react-router-dom";

/**
 * Shared chrome for every interactive demo: back link to the demos block,
 * title + one-line hook, a "linked experiment" strip pointing at the project
 * the demo is built from, the interactive body, and an honest-numbers footer
 * band in the figure-card style. Demos only provide the body.
 */
export function DemoShell({
  title,
  hook,
  projectId,
  footerLines,
  children,
}: {
  title: string;
  hook: string;
  projectId: string;
  footerLines: string[];
  children: ReactNode;
}) {
  return (
    <div className="demo-shell">
      <nav className="demo-topbar">
        <Link to="/projects#demos" className="demo-back">
          ← demos
        </Link>
      </nav>
      <header className="demo-header">
        <h1 className="demo-title">{title}</h1>
        <p className="demo-hook">{hook}</p>
        <p className="demo-experiment-strip">
          linked experiment →{" "}
          <Link to={`/projects/${projectId}`}>{projectId}</Link>
        </p>
      </header>
      {children}
      <footer className="figure-card demo-footer">
        <div className="figure-card-band">
          {footerLines.map((line) => (
            <p key={line} className="demo-footer-line">
              {line}
            </p>
          ))}
        </div>
      </footer>
    </div>
  );
}
