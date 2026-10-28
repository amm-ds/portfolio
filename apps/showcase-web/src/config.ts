// Central site configuration — single source of truth for site-wide values.
// Every value is overridable at build time via `import.meta.env.VITE_*`.

const env = import.meta.env as Record<string, string | undefined>;

/** Short brand suffix appended to document titles by the SEO hook. */
export const SITE_TITLE_SUFFIX = "amm-ds";

/** Full public site URL, no trailing slash. GitHub Pages until a domain exists. */
export const SITE_URL: string = (
  env.VITE_SITE_URL ?? "https://amm-ds.github.io/portfolio"
).replace(/\/+$/, "");

/** Origin of the deployed site, e.g. "https://amm-ds.github.io". */
export const SITE_ORIGIN: string = new URL(SITE_URL).origin;

/** Base path the SPA is served under, e.g. "/portfolio" ("" when served at root). */
export const SITE_BASE_PATH: string = new URL(SITE_URL).pathname.replace(/\/+$/, "");

/** Single site identity — used by title, og tags and nav brand. */
export const SITE_NAME = "amm-ds — ML/AI Engineering Portfolio";

export const REPO_URL = env.VITE_REPO_URL ?? "https://github.com/amm-ds/portfolio";
export const DOCS_URL = env.VITE_DOCS_URL ?? SITE_URL;
export const LINKEDIN_URL =
  env.VITE_LINKEDIN_URL ??
  "https://www.linkedin.com/in/alejandro-m%C3%A9rida-maroto-6a380615b/";

/** Contact address placeholder — one place for contact copy. */
export const CONTACT_EMAIL = env.VITE_CONTACT_EMAIL ?? "amm.datascience@gmail.com";

// Legacy alias kept for existing consumers (Footer, Contact, their tests).
export const SITE_EMAIL = CONTACT_EMAIL;

/** Availability copy — one place for engagement status. */
export const AVAILABILITY = {
  status: env.VITE_AVAILABILITY_STATUS ?? "Available for engagements",
  replyHours: Number(env.VITE_AVAILABILITY_REPLY_HOURS ?? 48),
} as const;

/** Absolute URL for a site path, honoring SITE_BASE_PATH. */
export function absoluteUrl(path = "/"): string {
  const suffix = path === "/" ? "" : path.startsWith("/") ? path : `/${path}`;
  return `${SITE_URL}${suffix}`;
}
