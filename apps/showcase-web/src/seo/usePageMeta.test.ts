import { renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SITE_URL } from "../config";
import { usePageMeta } from "./usePageMeta";

function metaContent(attribute: "name" | "property", key: string): string | null {
  return document.head
    .querySelector<HTMLElement>(`meta[${attribute}="${key}"]`)
    ?.getAttribute("content") ?? null;
}

describe("usePageMeta", () => {
  it("sets title, description, canonical and og tags", () => {
    const { unmount } = renderHook(() =>
      usePageMeta({
        title: "Services",
        description: "Consulting services",
        canonical: "/services",
      }),
    );

    expect(document.title).toBe("Services · alejandromerida.dev");
    expect(metaContent("name", "description")).toBe("Consulting services");
    expect(metaContent("property", "og:title")).toBe("Services · alejandromerida.dev");
    expect(metaContent("property", "og:description")).toBe("Consulting services");
    expect(metaContent("property", "og:url")).toBe(`${SITE_URL}/services`);
    expect(document.head.querySelector('link[rel="canonical"]')?.getAttribute("href")).toBe(
      `${SITE_URL}/services`,
    );
    expect(metaContent("name", "robots")).toBeNull();

    unmount();
  });

  it("does not double-append the brand suffix", () => {
    const { unmount } = renderHook(() =>
      usePageMeta({ title: "alejandromerida.dev", description: "brand" }),
    );
    expect(document.title).toBe("alejandromerida.dev");
    unmount();
  });

  it("emits robots noindex when requested and removes it otherwise", () => {
    const { rerender } = renderHook(
      ({ noindex }: { noindex: boolean }) =>
        usePageMeta({ title: "Draft", description: "hidden", noindex }),
      { initialProps: { noindex: true } },
    );
    expect(metaContent("name", "robots")).toBe("noindex");
    rerender({ noindex: false });
    expect(metaContent("name", "robots")).toBeNull();
  });

  it("updates tags in place on change and leaves the last route's values after unmount", () => {
    document.title = "original";
    const { rerender, unmount } = renderHook(
      ({ title }: { title: string }) => usePageMeta({ title, description: `${title} desc` }),
      { initialProps: { title: "First" } },
    );
    const descriptionEl = document.head.querySelector('meta[name="description"]');
    const ogTitleEl = document.head.querySelector('meta[property="og:title"]');
    const canonicalEl = document.head.querySelector('link[rel="canonical"]');
    expect(document.title).toBe("First · alejandromerida.dev");
    expect(metaContent("name", "description")).toBe("First desc");

    rerender({ title: "Second" });
    // same elements updated in place — no remove/re-add between routes
    expect(document.head.querySelector('meta[name="description"]')).toBe(descriptionEl);
    expect(document.head.querySelector('meta[property="og:title"]')).toBe(ogTitleEl);
    expect(document.head.querySelector('link[rel="canonical"]')).toBe(canonicalEl);
    expect(document.title).toBe("Second · alejandromerida.dev");
    expect(metaContent("name", "description")).toBe("Second desc");

    // unmounting leaves the head valid: the next route overwrites it in place
    unmount();
    expect(document.title).toBe("Second · alejandromerida.dev");
    expect(metaContent("name", "description")).toBe("Second desc");
    expect(metaContent("property", "og:title")).toBe(
      "Second · alejandromerida.dev",
    );
    expect(document.head.querySelector('link[rel="canonical"]')).toBe(canonicalEl);
  });
});
