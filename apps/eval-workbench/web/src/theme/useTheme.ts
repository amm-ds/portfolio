import { useEffect, useState } from "react";

export type Theme = "dark" | "light";
const STORAGE_KEY = "eval-workbench-theme";

function initialTheme(): Theme {
  try {
    return window.localStorage.getItem(STORAGE_KEY) === "light" ? "light" : "dark";
  } catch {
    return "dark";
  }
}

export function useTheme(): { theme: Theme; setTheme: (theme: Theme) => void } {
  const [theme, setTheme] = useState<Theme>(initialTheme);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;
    try {
      window.localStorage.setItem(STORAGE_KEY, theme);
    } catch {
      // The control still works when browser storage is unavailable.
    }
  }, [theme]);
  return { theme, setTheme };
}
