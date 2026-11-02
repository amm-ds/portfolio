import { NavLink } from "react-router-dom";
import { REPO_URL, SITE_NAME } from "../config";

export function Nav() {
  return (
    <div className="nav">
      <div className="nav-inner">
        <NavLink to="/" className="nav-brand">
          {SITE_NAME}
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
    </div>
  );
}
