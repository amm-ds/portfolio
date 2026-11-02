import { Link } from "react-router-dom";
import { REPO_URL, SITE_EMAIL, SITE_NAME } from "../config";

/** Single-line footer: nav links + GitHub + contact email. The copyright and
 * license line lives at the bottom of the About page. */
export function Footer() {
  return (
    <footer className="footer">
      <nav className="footer-nav" aria-label="Footer">
        <span className="footer-name">{SITE_NAME}</span>
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
    </footer>
  );
}
