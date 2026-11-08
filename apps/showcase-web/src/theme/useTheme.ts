import { useEffect, useSyncExternalStore } from "react";

export type Theme = "dark" | "light";

export const THEME_STORAGE_KEY = "portfolio-theme";

export const THEME_META_COLORS: Record<Theme, string> = {
  dark: "#0f172a",
  light: "#f5f8fc",
};

let currentTheme: Theme | null = null;
const listeners = new Set<() => void>();

function storedTheme(): Theme {
  try {
    return window.localStorage.getItem(THEME_STORAGE_KEY) === "light" ? "light" : "dark";
  } catch {
    return "dark";
  }
}

function initialTheme(): Theme {
  const attr = document.documentElement.dataset.theme;
  if (attr === "dark" || attr === "light") return attr;
  return storedTheme();
}

function getSnapshot(): Theme {
  if (currentTheme === null) currentTheme = initialTheme();
  return currentTheme;
}

function persistTheme(theme: Theme): void {
  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, theme);
  } catch {
    // Theme persistence is a convenience; the site remains usable without it.
  }
}

export function applyTheme(theme: Theme): void {
  document.documentElement.dataset.theme = theme;
  document.documentElement.style.colorScheme = theme;
  document
    .querySelector('meta[name="theme-color"]')
    ?.setAttribute("content", THEME_META_COLORS[theme]);
}

export function setSiteTheme(theme: Theme): void {
  currentTheme = theme;
  applyTheme(theme);
  persistTheme(theme);
  for (const listener of listeners) listener();
}

/** Test-only reset: simulate a fresh browser context importing the module. */
export function resetThemeStoreForTests(): void {
  currentTheme = null;
}

function subscribeTheme(listener: () => void): () => void {
  listeners.add(listener);
  const onStorage = (event: StorageEvent) => {
    if (event.key !== THEME_STORAGE_KEY) return;
    setSiteTheme(event.newValue === "light" ? "light" : "dark");
  };
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", onStorage);
  };
}

export function useTheme(): { theme: Theme; setTheme: (theme: Theme) => void } {
  const theme = useSyncExternalStore(subscribeTheme, getSnapshot, getSnapshot);
  useEffect(() => {
    applyTheme(theme);
  }, [theme]);
  return { theme, setTheme: setSiteTheme };
}
