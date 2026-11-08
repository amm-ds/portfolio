import type { Theme } from "./useTheme";
import { LIGHT_TRACE_COLOR_MAP } from "./plotlyTraceColors";

/** Same-origin report-frame theme bridge.
 *
 * The evaluation reports served at `/projects/:id/report` are committed
 * artifacts with a baked-in dark palette. Rather than mutate report source,
 * ReportView injects this small bridge into the frame's `srcDoc`: it stamps
 * `data-theme` on the report root, adds keyboard access to scrollable report
 * tables, and layers theme styles over the frame. Light mode also applies a
 * light-surface palette, a conservative Plotly relayout of the chrome, and a
 * trace-color restyle so the dark-authored graphs keep their contrast; dark
 * mode keeps the committed look apart from small accessibility fixes.
 */

export const REPORT_THEME_BRIDGE_BEGIN = "<!-- report-theme-bridge -->";
export const REPORT_THEME_BRIDGE_END = "<!-- /report-theme-bridge -->";

const BRIDGE_BLOCK_RE = /<!-- report-theme-bridge -->[\s\S]*?<!-- \/report-theme-bridge -->/g;

/** Minimal dark-mode accessibility fixes layered over the committed report
 * without changing its dark surfaces or data visualizations. */
const DARK_REPORT_CSS = `
code a, a code { color: #7dd3fc; }
.table-wrap:focus { outline: 2px solid #38bdf8; outline-offset: 2px; }
`;

/** Light-surface palette for the report: professional off-white/white
 * surfaces with the site's darker teal/blue accents (teal-700 / sky-700,
 * the readable-on-light counterparts of the dark theme's #2dd4bf / #38bdf8).
 * Selectors intentionally mirror the committed report style block; the
 * bridge loads after it, so equal-specificity rules here win. */
const LIGHT_REPORT_CSS = `
html { color-scheme: light; }
body { background: #f8fafc; color: #1e293b; }
h1 { color: #0f766e; }
h2, h3 { color: #0369a1; }
a { color: #0369a1; }
code a, a code { color: #0b625b; }
th, td { border-color: #cbd5e1; }
th { background: #e2e8f0; color: #0f172a; }
code { background: #e2e8f0; color: #0b625b; }
hr { border-color: #cbd5e1; }
.table-wrap:focus { outline: 2px solid #0369a1; outline-offset: 2px; }
`;

/** Plotly layout overrides for light mode: chrome (backgrounds, fonts,
 * axes, grid, legend) plus the template colorway, from which Plotly derives
 * implicit trace colors. Explicit per-trace colors are handled by the
 * trace-color restyle below, not by this relayout. */
const LIGHT_PLOTLY_RELAYOUT = JSON.stringify({
  "paper_bgcolor": "#ffffff",
  "plot_bgcolor": "#ffffff",
  "font.color": "#334155",
  "title.font.color": "#0f172a",
  "legend.font.color": "#334155",
  "legend.bgcolor": "rgba(0,0,0,0)",
  "xaxis.gridcolor": "#e2e8f0",
  "xaxis.linecolor": "#cbd5e1",
  "xaxis.tickfont.color": "#475569",
  "xaxis.title.font.color": "#334155",
  "xaxis.zerolinecolor": "#cbd5e1",
  "yaxis.gridcolor": "#e2e8f0",
  "yaxis.linecolor": "#cbd5e1",
  "yaxis.tickfont.color": "#475569",
  "yaxis.title.font.color": "#334155",
  "yaxis.zerolinecolor": "#cbd5e1",
});

/** Light-mode trace colors come from theme/plotlyTraceColors.ts (shared with
 * components/PlotlyFigure.tsx): report graphs are authored with the site's
 * dark palette (portfolio_core.plotting), whose light-on-dark accents wash
 * out on the light surface. Exact lowercase-string matches only — plotly
 * defaults and rgba() washes stay as committed. */

/** In-frame script: stamps the theme on the report root, makes scrollable
 * report tables keyboard-focusable, and — in light mode only — waits for the
 * report's own Plotly graphs to finish plotting, then relayouts their chrome
 * and restyles their trace colors to the light palette. Never throws: a
 * report without Plotly, or with the CDN unreachable, simply keeps its
 * committed look. */
function reportThemeScript(theme: Theme): string {
  const head = [
    "(function () {",
    '  "use strict";',
    `  var theme = ${JSON.stringify(theme)};`,
    "  try {",
    '    if (document.documentElement) document.documentElement.setAttribute("data-theme", theme);',
    "  } catch (err) { /* stamping is best-effort */ }",
    "  function markScrollableTables() {",
    "    try {",
    "      var wraps = document.querySelectorAll('.table-wrap');",
    "      for (var i = 0; i < wraps.length; i++) {",
    '        if (!wraps[i].hasAttribute("tabindex")) wraps[i].setAttribute("tabindex", "0");',
    "      }",
    "    } catch (err) { /* accessibility stamping is best-effort */ }",
    "  }",
    "  if (document.readyState === 'loading') {",
    "    document.addEventListener('DOMContentLoaded', markScrollableTables);",
    "  } else {",
    "    markScrollableTables();",
    "  }",
  ];
  if (theme !== "light") return [...head, "})();"].join("\n");
  return [
    ...head,
    `  var OVERRIDES = ${LIGHT_PLOTLY_RELAYOUT};`,
    `  var TRACE_COLORS = ${JSON.stringify(LIGHT_TRACE_COLOR_MAP)};`,
    "  var MAX_TRIES = 20;",
    "  var DELAY_MS = 150;",
    "  var tries = 0;",
    "  function remapColor(color) {",
    "    if (typeof color !== 'string') return null; // no exact match",
    "    var mapped = TRACE_COLORS[color.toLowerCase()];",
    "    return mapped === undefined ? null : mapped;",
    "  }",
    "  function remapColorList(colors) {",
    "    if (!Array.isArray(colors)) return null;",
    "    var mappedList = [];",
    "    var changed = false;",
    "    for (var i = 0; i < colors.length; i++) {",
    "      var mappedEntry = remapColor(colors[i]);",
    "      if (mappedEntry === null) {",
    "        mappedList.push(colors[i]);",
    "      } else {",
    "        mappedList.push(mappedEntry);",
    "        changed = true;",
    "      }",
    "    }",
    "    return changed ? mappedList : null;",
    "  }",
    "  function addRestyle(update, attr, index, value) {",
    "    if (!update[attr]) update[attr] = { indices: [], values: [] };",
    "    update[attr].indices.push(index);",
    "    update[attr].values.push(value);",
    "  }",
    "  function restyleTraces(graph, plotly) {",
    "    var update = {};",
    "    for (var i = 0; i < graph.data.length; i++) {",
    "      var trace = graph.data[i] || {};",
    "      var lineColor = remapColor(trace.line && trace.line.color);",
    "      if (lineColor !== null) addRestyle(update, 'line.color', i, lineColor);",
    "      var marker = trace.marker || {};",
    "      var markerColor = remapColor(marker.color);",
    "      if (markerColor === null) markerColor = remapColorList(marker.color);",
    "      if (markerColor !== null) addRestyle(update, 'marker.color', i, markerColor);",
    "      var markerColors = remapColorList(marker.colors);",
    "      if (markerColors !== null) addRestyle(update, 'marker.colors', i, markerColors);",
    "      var fillColor = remapColor(trace.fillcolor);",
    "      if (fillColor !== null) addRestyle(update, 'fillcolor', i, fillColor);",
    "    }",
    "    var attrs = Object.keys(update);",
    "    for (var k = 0; k < attrs.length; k++) {",
    "      var patch = {};",
    "      patch[attrs[k]] = update[attrs[k]].values;",
    "      plotly.restyle(graph, patch, update[attrs[k]].indices);",
    "    }",
    "  }",
    // Most committed figures leave trace colors implicit and carry the palette
    // as the template colorway; Plotly derives implicit colors from it, and a
    // relayout of the colorway re-derives them (verified against plotly.js-dist-min).
    "  function mappedColorway(graph) {",
    "    var layout = graph.layout || {};",
    "    var tpl = layout.template || {};",
    "    var nested = tpl.layout || {};",
    "    return remapColorList(nested.colorway || tpl.colorway);",
    "  }",
    // Titles bake inline `color:#…` spans for the dark surface; light mode
    // rewrites them to a readable slate (mirrors titleLayout in PlotlyFigure).
    "  function forcedTitleText(graph) {",
    "    var text = graph.layout && graph.layout.title && graph.layout.title.text;",
    "    if (typeof text !== 'string' || text.indexOf('color:') === -1) return null;",
    "    var rewritten = text.replace(/color\\s*:\\s*'?#[0-9a-fA-F]{3,8}'?/gi, 'color:#475569');",
    "    return rewritten === text ? null : rewritten;",
    "  }",
    "  function relayoutGraphs() {",
    "    try {",
    "      var graphs = document.querySelectorAll('.plotly-graph-div');",
    "      if (!graphs.length) return true; // no graphs to re-theme",
    "      var plotly = window.Plotly;",
    "      if (!plotly || typeof plotly.relayout !== 'function' || typeof plotly.restyle !== 'function') return false;",
    "      var done = true;",
    "      for (var i = 0; i < graphs.length; i++) {",
    "        var graph = graphs[i];",
    "        if (!graph.data) { done = false; continue; } // not plotted yet",
    "        var overrides = Object.assign({}, OVERRIDES);",
    "        var colorway = mappedColorway(graph);",
    "        if (colorway !== null) overrides['template.layout.colorway'] = colorway;",
    "        var titleText = forcedTitleText(graph);",
    "        if (titleText !== null) overrides['title.text'] = titleText;",
    "        plotly.relayout(graph, overrides);",
    "        restyleTraces(graph, plotly);",
    "      }",
    "      return done;",
    "    } catch (err) {",
    "      return true; // unexpected state: stop polling quietly",
    "    }",
    "  }",
    "  function attempt() {",
    "    if (relayoutGraphs()) return;",
    "    tries += 1;",
    "    if (tries >= MAX_TRIES) return;",
    "    setTimeout(attempt, DELAY_MS);",
    "  }",
    "  if (document.readyState === 'loading') {",
    "    document.addEventListener('DOMContentLoaded', attempt);",
    "  } else {",
    "    attempt();",
    "  }",
    "})();",
  ].join("\n");
}

function buildReportThemeBridge(theme: Theme): string {
  const parts = [REPORT_THEME_BRIDGE_BEGIN];
  parts.push(`<style>${theme === "light" ? LIGHT_REPORT_CSS : DARK_REPORT_CSS}</style>`);
  parts.push(`<script>${reportThemeScript(theme)}</script>`);
  parts.push(REPORT_THEME_BRIDGE_END);
  return parts.join("");
}

/** Put `data-theme` on the frame document's root tag. An existing
 * `data-theme` attribute is replaced, never duplicated. */
function stampThemeOnRoot(srcDoc: string, theme: Theme): string {
  return srcDoc.replace(/<html\b[^>]*>/i, (tag) =>
    /\sdata-theme\s*=\s*("[^"]*"|'[^']*')/i.test(tag)
      ? tag.replace(/\sdata-theme\s*=\s*("[^"]*"|'[^']*')/i, ` data-theme="${theme}"`)
      : tag.replace(/^<html/i, `<html data-theme="${theme}"`),
  );
}

/** Inject the theme bridge into a report document.
 *
 * Idempotent: a previously injected bridge block is replaced, not stacked,
 * and an existing root `data-theme` is re-stamped. The bridge goes before
 * `</body>` when present and is appended to a malformed/missing-body
 * document instead of failing. The report markup itself is never mutated —
 * the bridge only wraps it. */
export function injectReportThemeBridge(srcDoc: string, theme: Theme): string {
  const stripped = srcDoc.replace(BRIDGE_BLOCK_RE, "");
  const stamped = stampThemeOnRoot(stripped, theme);
  const bridge = buildReportThemeBridge(theme);
  const bodyClose = /<\/body\s*>/i.exec(stamped);
  if (!bodyClose) return stamped + bridge;
  return stamped.slice(0, bodyClose.index) + bridge + stamped.slice(bodyClose.index);
}
