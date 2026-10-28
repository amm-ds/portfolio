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
 * Dependency-free; everything it touches is removed on unmount/change.
 */
export function usePageMeta({ title, description, canonical, noindex }: PageMetaProps): void {
  useEffect(() => {
    const previousTitle = document.title;
    const fullTitle = title.endsWith(SITE_TITLE_SUFFIX) ? title : `${title} · ${SITE_TITLE_SUFFIX}`;
    document.title = fullTitle;

    const owned: Element[] = [];
    owned.push(upsertMeta("name", "description", description));
    owned.push(upsertMeta("property", "og:title", fullTitle));
    owned.push(upsertMeta("property", "og:description", description));
    owned.push(upsertMeta("property", "og:url", resolveCanonical(canonical)));
    if (noindex) owned.push(upsertMeta("name", "robots", "noindex"));

    let canonicalLink = document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]');
    if (!canonicalLink) {
      canonicalLink = document.createElement("link");
      canonicalLink.setAttribute("rel", "canonical");
      document.head.appendChild(canonicalLink);
    }
    canonicalLink.setAttribute("href", resolveCanonical(canonical));
    owned.push(canonicalLink);

    return () => {
      document.title = previousTitle;
      for (const el of owned) el.remove();
    };
  }, [title, description, canonical, noindex]);
}

/** Component wrapper around usePageMeta for declarative route usage. */
export function PageMeta(props: PageMetaProps) {
  usePageMeta(props);
  return null;
}
