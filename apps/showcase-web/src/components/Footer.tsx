import { Link } from "react-router-dom";
import { SITE_EMAIL } from "../config";

export function Footer() {
  return (
    <footer className="footer">
      <div className="footer-inner">
        <div className="footer-brand">
          <p className="footer-name">amm-ds</p>
          <p className="footer-tagline">
            Data Scientist &amp; ML Engineer — end-to-end ML/AI systems
          </p>
        </div>
        <nav className="footer-nav" aria-label="Footer">
          <Link to="/projects">Experiments</Link>
          <Link to="/services">Services</Link>
          <Link to="/contact">Contact</Link>
          <a href="https://github.com/amm-ds/portfolio" target="_blank" rel="noreferrer">
            GitHub
          </a>
          <a href={`mailto:${SITE_EMAIL}`} className="footer-email">
            {SITE_EMAIL}
          </a>
        </nav>
      </div>
      <p className="footer-small">© 2026 amm-ds · MIT licensed</p>
    </footer>
  );
}
