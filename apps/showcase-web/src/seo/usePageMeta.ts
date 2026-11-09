import { useEffect } from "react";
import { SITE_TITLE_SUFFIX, SITE_URL, absoluteUrl } from "../config";

export interface PageMetaProps {
  title: string;
  description: string;
  /** Canonical path ("/services") or absolute URL. Defaults to the current location. */
  canonical?: string;
  noindex?: boolean;
}

function upsertMeta(attribute: "name" | "property", key: string, content: string): HTMLElement {
  let el = document.head.querySelector<HTMLElement>(`meta[${attribute}="${key}"]`);
  if (!el) {
    el = document.createElement("meta");
    el.setAttribute(attribute, key);
    document.head.appendChild(el);
  }
  el.setAttribute("content", content);
  return el;
}

function resolveCanonical(canonical: string | undefined): string {
  if (canonical) {
    return /^https?:\/\//.test(canonical) ? canonical : absoluteUrl(canonical);
  }
  return `${SITE_URL}${window.location.pathname}`;
}

/**
 * Sets document.title and per-route meta tags (description, canonical,
 * og:title/og:description/og:url, robots noindex) via direct DOM manipulation.
 * Existing tags are updated in place — created only when absent — so route
 * changes never remove and re-add them; the head keeps valid values between
 * routes instead of flickering back to the shell defaults. The last route's
 * values stay in the head after unmount (there is no next route to describe).
 */
export function usePageMeta({ title, description, canonical, noindex }: PageMetaProps): void {
  useEffect(() => {
    const fullTitle = title.endsWith(SITE_TITLE_SUFFIX) ? title : `${title} · ${SITE_TITLE_SUFFIX}`;
    document.title = fullTitle;

    upsertMeta("name", "description", description);
    upsertMeta("property", "og:title", fullTitle);
    upsertMeta("property", "og:description", description);
    upsertMeta("property", "og:url", resolveCanonical(canonical));

    let canonicalLink = document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]');
    if (!canonicalLink) {
      canonicalLink = document.createElement("link");
      canonicalLink.setAttribute("rel", "canonical");
      document.head.appendChild(canonicalLink);
    }
    canonicalLink.setAttribute("href", resolveCanonical(canonical));

    if (noindex) {
      upsertMeta("name", "robots", "noindex");
    } else {
      document.head.querySelector('meta[name="robots"]')?.remove();
    }
  }, [title, description, canonical, noindex]);
}
