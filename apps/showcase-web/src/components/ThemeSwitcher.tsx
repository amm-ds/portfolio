import { useTheme } from "../theme/useTheme";

export function ThemeSwitcher() {
  const { theme, setTheme } = useTheme();
  return (
    <div className="theme-switcher" role="group" aria-label="Display theme">
      <button
        type="button"
        className={`theme-switcher__option ${theme === "dark" ? "is-active" : ""}`}
        aria-pressed={theme === "dark"}
        onClick={() => setTheme("dark")}
      >
        <span aria-hidden="true">☾</span>
        dark
      </button>
      <button
        type="button"
        className={`theme-switcher__option ${theme === "light" ? "is-active" : ""}`}
        aria-pressed={theme === "light"}
        onClick={() => setTheme("light")}
      >
        <span aria-hidden="true">☼</span>
        light
      </button>
    </div>
  );
}
