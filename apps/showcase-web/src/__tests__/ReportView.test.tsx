import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { readStylesCss } from "./helpers/css";
import { App } from "../App";
import { ReportView } from "../pages/ReportView";
import {
  injectReportThemeBridge,
  REPORT_THEME_BRIDGE_BEGIN,
  REPORT_THEME_BRIDGE_END,
} from "../theme/reportBridge";
import { THEME_STORAGE_KEY } from "../theme/useTheme";

/** A committed-style report document: one inline style (the constrained
 * reading column the report template ships) and a heading. */
const REPORT_HTML = `<!doctype html><html><head><meta charset="utf-8">
<style>body { max-width: 1400px; margin: 2.5rem auto; }</style></head>
<body><h1>Evaluation report</h1><p>numbers</p></body></html>`;

function htmlResponse(): Response {
  return new Response(REPORT_HTML, {
    status: 200,
    headers: { "Content-Type": "text/html" },
  });
}

function renderReport(id = "01-rag-agent") {
  return render(
    <MemoryRouter initialEntries={[`/projects/${id}/report`]}>
      <Routes>
        <Route path="/projects/:id/report" element={<ReportView />} />
      </Routes>
    </MemoryRouter>,
  );
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  // leave no theme residue for the next test's initial read
  document.documentElement.removeAttribute("data-theme");
  window.localStorage.clear();
});

describe("ReportView", () => {
  it("renders the API-served report in a full-width shell with the theme bridge injected", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url =
          typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
        if (url.endsWith("/report")) return Promise.resolve(htmlResponse());
        return Promise.resolve(
          new Response(JSON.stringify({ detail: "no" }), {
            status: 404,
            headers: { "Content-Type": "application/json" },
          }),
        );
      }),
    );
    renderReport();
    const frame = (await screen.findByTitle(
      "Evaluation report: 01-rag-agent",
    )) as HTMLIFrameElement;
    expect(frame.classList.contains("report-frame")).toBe(true);
    expect(frame).toHaveAttribute("sandbox", "allow-scripts allow-same-origin");
    const doc = frame.getAttribute("srcdoc")!;
    // the committed report markup is preserved…
    expect(doc).toContain("<h1>Evaluation report</h1>");
    expect(doc).toContain("max-width: 1400px");
    // …and the default (dark) theme is stamped on the frame root with only
    // small accessibility fixes over the committed report styling
    expect(doc).toContain('<html data-theme="dark">');
    expect(doc).toContain(REPORT_THEME_BRIDGE_BEGIN);
    expect(doc).toContain(REPORT_THEME_BRIDGE_END);
    expect(doc).toContain("code a, a code");
    expect(doc).toContain("markScrollableTables");
    expect(doc).not.toContain("color-scheme: light");
    // the bridge sits before </body>
    expect(doc.indexOf(REPORT_THEME_BRIDGE_BEGIN)).toBeLessThan(doc.indexOf("</body>"));
    // Full-width/source decoration belongs to the API document, not a second
    // React-side injection that direct API routes would bypass.
    expect(document.querySelector(".report-source")).toBeNull();
    // the view spans the full page width like every other page
    const css = readStylesCss();
    expect(css.match(/\.report-view \{[\s\S]*?\n\}/)![0]).toContain("width: 100%;");
    expect(css.match(/\.report-view \.report-frame \{[\s\S]*?\n\}/)![0]).toContain(
      "width: 100%;",
    );
  });

  it("injects light-surface overrides when the active theme is light", async () => {
    window.localStorage.setItem(THEME_STORAGE_KEY, "light");
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(htmlResponse())));
    renderReport();
    const frame = (await screen.findByTitle(
      "Evaluation report: 01-rag-agent",
    )) as HTMLIFrameElement;
    const doc = frame.getAttribute("srcdoc")!;
    // theme markup on the frame root
    expect(doc).toContain('<html data-theme="light">');
    // readable off-white/white surface with the site's darker teal/blue accents
    expect(doc).toContain("color-scheme: light");
    expect(doc).toContain("background: #f8fafc");
    expect(doc).toContain("color: #1e293b");
    expect(doc).toContain("color: #0f766e");
    expect(doc).toContain("color: #0369a1");
    // conservative Plotly chrome relayout (backgrounds/fonts/axes/grid/legend)…
    expect(doc).toContain('"paper_bgcolor":"#ffffff"');
    expect(doc).toContain('"plot_bgcolor":"#ffffff"');
    expect(doc).toContain('"xaxis.gridcolor"');
    expect(doc).toContain('"legend.font.color"');
    // …and a trace-color restyle: dark-authored palette hexes map to their
    // light-surface counterparts; unknown colors are never in the table
    expect(doc).toContain("TRACE_COLORS");
    expect(doc).toContain("restyleTraces");
    expect(doc).toContain('"#2dd4bf":"#14b8a6"');
    expect(doc).toContain('"#64748b":"#475569"');
    // …plus the template colorway, from which implicit trace colors derive
    expect(doc).toContain("mappedColorway");
    expect(doc).toContain("template.layout.colorway");
    // …and title inline spans authored with dark-surface colors
    expect(doc).toContain("forcedTitleText");
    expect(doc).toContain("title.text");
    // committed report markup still intact, bridge layered after it
    expect(doc).toContain("<h1>Evaluation report</h1>");
    expect(doc.indexOf("<h1>Evaluation report</h1>")).toBeLessThan(
      doc.indexOf(REPORT_THEME_BRIDGE_BEGIN),
    );
  });

  it("re-applies the frame theme when the app shell theme changes", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(htmlResponse())));
    renderReport();
    const frame = (await screen.findByTitle(
      "Evaluation report: 01-rag-agent",
    )) as HTMLIFrameElement;
    expect(frame.getAttribute("srcdoc")).toContain('<html data-theme="dark">');
    expect(frame.getAttribute("srcdoc")).not.toContain("color-scheme: light");
    // what applyTheme writes when the user toggles the switcher
    act(() => {
      document.documentElement.setAttribute("data-theme", "light");
    });
    await waitFor(() =>
      expect(frame.getAttribute("srcdoc")).toContain('<html data-theme="light">'),
    );
    expect(frame.getAttribute("srcdoc")).toContain("color-scheme: light");
    // and back to dark
    act(() => {
      document.documentElement.setAttribute("data-theme", "dark");
    });
    await waitFor(() => expect(frame.getAttribute("srcdoc")).toContain('<html data-theme="dark">'));
    expect(frame.getAttribute("srcdoc")).not.toContain("color-scheme: light");
  });

  it("shows an unavailable state with a way back when the report 404s", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(JSON.stringify({ detail: "no report yet" }), {
            status: 404,
            headers: { "Content-Type": "application/json" },
          }),
        ),
      ),
    );
    renderReport("05-ml-pipeline-churn");
    await screen.findByText(/report unavailable/i);
    const back = screen.getByRole("link", { name: /back to the case study/i });
    expect(back.getAttribute("href")).toBe("/projects/05-ml-pipeline-churn");
    expect(document.querySelector(".report-frame")).toBeNull();
  });

  it("shows a retryable error for a 500 instead of claiming the report is unpublished", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response("server error", { status: 500 }))
      .mockImplementationOnce(() => Promise.resolve(htmlResponse()));
    vi.stubGlobal("fetch", fetchMock);
    renderReport();

    await screen.findByText(/report could not be loaded/i);
    expect(screen.queryByText(/no evaluation report has been published/i)).toBeNull();
    screen.getByRole("button", { name: "Retry" }).click();
    expect(await screen.findByTitle("Evaluation report: 01-rag-agent")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("is routed inside the App shell at /projects/:id/report, full width with the footer kept", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response("[]", {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
    render(
      <MemoryRouter initialEntries={["/projects/01-rag-agent/report"]}>
        <App />
      </MemoryRouter>,
    );
    const frame = await screen.findByTitle("Evaluation report: 01-rag-agent");
    expect(frame).not.toBeNull();
    // the report view rides the fluid shell like every other page
    expect(document.querySelector("main")!.className).toContain("app-main--fluid");
    expect(document.querySelector(".footer")).not.toBeNull();
  });
});

describe("reportThemeBridge", () => {
  it("stamps the theme on the root and injects the bridge before </body>", () => {
    const doc = injectReportThemeBridge(REPORT_HTML, "light");
    expect(doc).toContain('<html data-theme="light">');
    expect(doc.indexOf(REPORT_THEME_BRIDGE_BEGIN)).toBeLessThan(doc.indexOf("</body>"));
    expect(doc.indexOf(REPORT_THEME_BRIDGE_END)).toBeLessThan(doc.indexOf("</body>"));
    // committed markup untouched around the bridge
    expect(doc).toContain("<h1>Evaluation report</h1>");
    expect(doc).toContain("</html>");
  });

  it("is idempotent: re-injection replaces instead of stacking", () => {
    const once = injectReportThemeBridge(REPORT_HTML, "light");
    const twice = injectReportThemeBridge(once, "light");
    expect(twice).toBe(once);
    expect(twice.match(/<!-- report-theme-bridge -->/g)!.length).toBe(1);
    expect(twice.match(/data-theme=/g)!.length).toBe(1);
    // re-theming swaps the stamp and drops the old theme's overrides
    const dark = injectReportThemeBridge(twice, "dark");
    expect(dark).toContain('<html data-theme="dark">');
    expect(dark).not.toContain('<html data-theme="light">');
    expect(dark).not.toContain("color-scheme: light");
    expect(dark.match(/<!-- report-theme-bridge -->/g)!.length).toBe(1);
  });

  it("re-stamps a pre-existing data-theme instead of duplicating it", () => {
    const stamped = injectReportThemeBridge('<html data-theme="dark" lang="en"><body></body></html>', "light");
    expect(stamped).toContain('<html data-theme="light" lang="en">');
    expect(stamped.match(/data-theme=/g)!.length).toBe(1);
  });

  it("appends the bridge instead of failing when </body> is missing", () => {
    const noBodyClose = "<html><body><p>truncated report</p>";
    const doc = injectReportThemeBridge(noBodyClose, "light");
    expect(doc).toContain("truncated report");
    expect(doc).toContain(REPORT_THEME_BRIDGE_BEGIN);
    expect(doc).toContain('<html data-theme="light">');
    expect(doc.indexOf(REPORT_THEME_BRIDGE_BEGIN)).toBeGreaterThan(
      doc.indexOf("truncated report"),
    );
  });

  it("handles an empty document", () => {
    const doc = injectReportThemeBridge("", "dark");
    expect(doc).toContain(REPORT_THEME_BRIDGE_BEGIN);
    expect(doc.match(/<!-- report-theme-bridge -->/g)!.length).toBe(1);
  });

  it("keeps dark styling while adding accessibility-only bridge fixes", () => {
    const doc = injectReportThemeBridge(REPORT_HTML, "dark");
    expect(doc).toContain('<html data-theme="dark">');
    const bridge = doc.slice(
      doc.indexOf(REPORT_THEME_BRIDGE_BEGIN),
      doc.indexOf(REPORT_THEME_BRIDGE_END),
    );
    expect(bridge).toContain("code a, a code");
    expect(bridge).toContain("markScrollableTables");
    expect(bridge).not.toContain("color-scheme: light");
    expect(bridge).not.toContain("paper_bgcolor");
    expect(bridge).not.toContain("relayout");
    // dark injects chrome relayout and trace restyle for nothing
    expect(bridge).not.toContain("TRACE_COLORS");
    expect(bridge).not.toContain("restyle");
  });
});
