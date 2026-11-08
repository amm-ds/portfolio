import type { ReactNode } from "react";
import { BusinessImplication } from "./BusinessImplication";

/** Shared section contract for full application case studies. */
export function AppArticleSection({
  id,
  index,
  title,
  subtitle,
  takeaway,
  children,
}: {
  id: string;
  index: number;
  title: string;
  subtitle: string;
  takeaway: string;
  children: ReactNode;
}) {
  return (
    <section id={id} className="story-section">
      <h2>
        <span className="sec-num">{String(index).padStart(2, "0")}</span>
        {title}
      </h2>
      <p className="section-subtitle">{subtitle}</p>
      <div className="story-main">
        {children}
        <BusinessImplication label="tl;dr">{takeaway}</BusinessImplication>
      </div>
    </section>
  );
}

/** Screenshots keep one full-size inspection path and one accessible caption. */
export function AppScreenshot({
  name,
  alt,
  caption,
}: {
  name: string;
  alt: string;
  caption: string;
}) {
  return (
    <figure className="app-screenshot">
      <a
        href={`/apps/${name}`}
        target="_blank"
        rel="noopener noreferrer"
        aria-label={`Open full image: ${alt}`}
      >
        <img src={`/apps/${name}`} alt={alt} loading="lazy" />
      </a>
      <figcaption>{caption}</figcaption>
    </figure>
  );
}
