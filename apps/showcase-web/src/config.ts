// Central site configuration — single source of truth for site-wide values.
// Every value is overridable at build time via `import.meta.env.VITE_*`.

const env = import.meta.env as Record<string, string | undefined>;

/** Short brand suffix appended to document titles by the SEO hook. */
export const SITE_TITLE_SUFFIX = "alejandromerida.dev";

/** Full public site URL, no trailing slash. */
export const SITE_URL: string = (
  env.VITE_SITE_URL ?? "https://alejandromerida.dev"
).replace(/\/+$/, "");

/** Origin of the deployed site, e.g. "https://alejandromerida.dev". */
export const SITE_ORIGIN: string = new URL(SITE_URL).origin;

/** Base path the SPA is served under, e.g. "/portfolio" ("" when served at root). */
export const SITE_BASE_PATH: string = new URL(SITE_URL).pathname.replace(/\/+$/, "");

/** Single site identity — used by title, og tags and nav brand. */
export const SITE_NAME = "alejandromerida.dev";

/** Nav brand split: the root keeps the default brand color, the ".dev" suffix
 * renders in the accent color. Concatenating the two yields SITE_NAME exactly,
 * so tests and assistive tech read the identical brand text. */
export const SITE_NAME_ROOT = SITE_NAME.replace(/\.dev$/, "");
export const SITE_NAME_SUFFIX = SITE_NAME.endsWith(".dev") ? ".dev" : "";

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
  replyHours: Number(env.VITE_AVAILABILITY_REPLY_HOURS ?? 24),
} as const;

/** Absolute URL for a site path, honoring SITE_BASE_PATH. */
export function absoluteUrl(path = "/"): string {
  const suffix = path === "/" ? "" : path.startsWith("/") ? path : `/${path}`;
  return `${SITE_URL}${suffix}`;
}
