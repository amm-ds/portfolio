import { LINKEDIN_URL, REPO_URL, SITE_NAME, absoluteUrl } from "../config";

export function PersonJsonLd() {
  const data = {
    "@context": "https://schema.org",
    "@type": "Person",
    name: SITE_NAME,
    url: absoluteUrl("/"),
    jobTitle: "Data Scientist, ML & AI Consultant",
    sameAs: [REPO_URL, LINKEDIN_URL],
  };
  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(data) }}
    />
  );
}

export interface SoftwareSourceCodeJsonLdProps {
  name: string;
  description: string;
  /** Project route, e.g. "/projects/01-rag-agent". */
  path: string;
}

export function SoftwareSourceCodeJsonLd({ name, description, path }: SoftwareSourceCodeJsonLdProps) {
  const data = {
    "@context": "https://schema.org",
    "@type": "SoftwareSourceCode",
    name,
    description,
    codeRepository: REPO_URL,
    url: absoluteUrl(path),
  };
  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(data) }}
    />
  );
}
