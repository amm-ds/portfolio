import { NavLink } from "react-router-dom";
import { REPO_URL, SITE_NAME_ROOT, SITE_NAME_SUFFIX } from "../config";

export function Nav() {
  return (
    <header className="nav">
      <div className="nav-inner">
        <NavLink to="/" className="nav-brand">
          {SITE_NAME_ROOT}
          <span className="nav-brand-accent">{SITE_NAME_SUFFIX}</span>
        </NavLink>
        <nav className="nav-links" aria-label="Primary">
          <NavLink to="/" end>
            Home
          </NavLink>
          <NavLink to="/projects">Projects</NavLink>
          <NavLink to="/services">Services</NavLink>
          <NavLink to="/about">About</NavLink>
          <NavLink to="/contact">Contact</NavLink>
          <a className="github" href={REPO_URL} target="_blank" rel="noreferrer">
            GitHub
          </a>
        </nav>
      </div>
    </header>
  );
}
