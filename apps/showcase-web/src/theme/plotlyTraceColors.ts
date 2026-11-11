/** Light-mode Plotly trace colors, single source of truth.
 *
 * Figure JSONs ship the site's dark palette (portfolio_core.plotting); its
 * light-on-dark accents wash out on the near-white light surface, so each
 * authored hex maps to its darker counterpart. Keys are lowercase; lookups
 * lowercase the payload color. Exact-string matches only — plotly defaults
 * and rgba() washes stay as committed. Dark mode uses no map at all.
 */
export const LIGHT_TRACE_COLOR_MAP: Record<string, string> = {
  "#64748b": "#475569",
  "#94a3b8": "#64748b",
  "#0f172a": "#1e293b",
  "#fbbf24": "#b45309",
  "#2dd4bf": "#14b8a6",
  "#38bdf8": "#0284c7",
  "#a78bfa": "#7c3aed",
  "#f472b6": "#db2777",
  "#34d399": "#059669",
  "#dc2626": "#b91c1c",
};
