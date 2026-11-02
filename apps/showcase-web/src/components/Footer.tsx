import { Link } from "react-router-dom";
import { REPO_URL, SITE_EMAIL, SITE_NAME_ROOT, SITE_NAME_SUFFIX } from "../config";

/** Two-zone single bar: brand + copyright on the left, nav links + GitHub +
 * contact email on the right. One visual line on desktop (space-between,
 * baseline-aligned), graceful wrap on mobile. The brand renders with the
 * header's treatment: "> " prefix, default text color, ".dev" accent suffix. */
export function Footer() {
  return (
    <footer className="footer">
      <div className="footer-bar">
        <div className="footer-brand">
          <span className="footer-name">
            {SITE_NAME_ROOT}
            <span className="footer-accent">{SITE_NAME_SUFFIX}</span>
          </span>
          <span className="footer-copy">© 2026</span>
        </div>
        <nav className="footer-nav" aria-label="Footer">
          <Link to="/projects">Projects</Link>
          <Link to="/services">Services</Link>
          <Link to="/about">About</Link>
          <Link to="/contact">Contact</Link>
          <Link to="/glossary">Glossary</Link>
          <a href={REPO_URL} target="_blank" rel="noreferrer">
            GitHub
          </a>
          <a href={`mailto:${SITE_EMAIL}`} className="footer-email">
            {SITE_EMAIL}
          </a>
        </nav>
      </div>
    </footer>
  );
}
