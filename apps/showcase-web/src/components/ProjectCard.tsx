import { Link } from "react-router-dom";
import type { Project } from "../api";

export function ProjectCard({ project }: { project: Project }) {
  return (
    <Link to={`/projects/${project.id}`} className="project-card">
      <div className="project-card-top">
        <div>
          <h3>{project.title}</h3>
          <p className="domain">{project.domain}</p>
        </div>
        <span className={`badge ${project.status}`}>[{project.status}]</span>
      </div>
      <div className="chips">
        {project.techniques.map((t) => (
          <span key={t} className="chip">
            {t}
          </span>
        ))}
      </div>
      <p className="data">
        <strong>Data:</strong> {project.data}
      </p>
    </Link>
  );
}
