// Apply the persisted site theme before React hydrates to avoid a flash.
// Kept as an external file (not an inline <script>) because the SPA's
// Content-Security-Policy is script-src 'self' with no unsafe-inline.
(() => {
  try {
    const theme = window.localStorage.getItem("portfolio-theme") === "light" ? "light" : "dark";
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;
    document
      .querySelector('meta[name="theme-color"]')
      ?.setAttribute("content", theme === "light" ? "#f5f8fc" : "#0f172a");
  } catch {
    // Storage can be unavailable in hardened browsers; dark remains the default.
  }
})();
