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

    expect(document.title).toBe("Services · amm-ds");
    expect(metaContent("name", "description")).toBe("Consulting services");
    expect(metaContent("property", "og:title")).toBe("Services · amm-ds");
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
      usePageMeta({ title: "amm-ds", description: "brand" }),
    );
    expect(document.title).toBe("amm-ds");
    unmount();
  });

  it("emits robots noindex when requested", () => {
    const { unmount } = renderHook(() =>
      usePageMeta({ title: "Draft", description: "hidden", noindex: true }),
    );
    expect(metaContent("name", "robots")).toBe("noindex");
    unmount();
  });

  it("cleans up on change and unmount", () => {
    document.title = "original";
    const { rerender, unmount } = renderHook(
      ({ title }: { title: string }) => usePageMeta({ title, description: `${title} desc` }),
      { initialProps: { title: "First" } },
    );
    expect(document.title).toBe("First · amm-ds");
    expect(metaContent("name", "description")).toBe("First desc");

    rerender({ title: "Second" });
    expect(document.title).toBe("Second · amm-ds");
    expect(metaContent("name", "description")).toBe("Second desc");

    unmount();
    expect(document.title).toBe("original");
    expect(metaContent("name", "description")).toBeNull();
    expect(metaContent("property", "og:title")).toBeNull();
    expect(document.head.querySelector('link[rel="canonical"]')).toBeNull();
  });
});
