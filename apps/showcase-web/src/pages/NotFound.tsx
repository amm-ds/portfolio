import { Link } from "react-router-dom";

/** Minimal terminal-styled 404 for unknown routes. */
export function NotFound() {
  return (
    <div className="state-box not-found">
      <p className="not-found-code">$ 404 — page not found</p>
      <p>
        The page you asked for is not here.{" "}
        <Link to="/">→ home</Link> · <Link to="/projects">→ projects</Link>
      </p>
    </div>
  );
}
