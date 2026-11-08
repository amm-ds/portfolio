import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { THEME_META_COLORS, THEME_STORAGE_KEY, resetThemeStoreForTests, useTheme } from "./useTheme";

let meta: HTMLMetaElement;

beforeEach(() => {
  window.localStorage.clear();
  delete document.documentElement.dataset.theme;
  document.documentElement.style.colorScheme = "";
  meta = document.createElement("meta");
  meta.setAttribute("name", "theme-color");
  meta.setAttribute("content", "#0f172a");
  document.head.append(meta);
  resetThemeStoreForTests();
});

afterEach(() => {
  resetThemeStoreForTests();
  window.localStorage.clear();
  delete document.documentElement.dataset.theme;
  document.documentElement.style.colorScheme = "";
  meta.remove();
});

describe("useTheme", () => {
  it("defaults to dark and applies document and meta colors", () => {
    const { result } = renderHook(() => useTheme());

    expect(result.current.theme).toBe("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(document.documentElement.style.colorScheme).toBe("dark");
    expect(meta.getAttribute("content")).toBe(THEME_META_COLORS.dark);
  });

  it("updates the document, meta color, and persisted theme", () => {
    const { result } = renderHook(() => useTheme());

    act(() => result.current.setTheme("light"));

    expect(result.current.theme).toBe("light");
    expect(document.documentElement.dataset.theme).toBe("light");
    expect(document.documentElement.style.colorScheme).toBe("light");
    expect(meta.getAttribute("content")).toBe(THEME_META_COLORS.light);
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe("light");
  });

  it("restores a persisted light theme on the next render", () => {
    window.localStorage.setItem(THEME_STORAGE_KEY, "light");
    const { result } = renderHook(() => useTheme());

    expect(result.current.theme).toBe("light");
    expect(document.documentElement.dataset.theme).toBe("light");
    expect(meta.getAttribute("content")).toBe(THEME_META_COLORS.light);
  });

  it("synchronizes independent hook instances through the shared store", () => {
    const first = renderHook(() => useTheme());
    const second = renderHook(() => useTheme());

    act(() => first.result.current.setTheme("light"));

    expect(first.result.current.theme).toBe("light");
    expect(second.result.current.theme).toBe("light");
    expect(document.documentElement.dataset.theme).toBe("light");
  });
});
