import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { readStylesCss } from "./helpers/css";
import { App } from "../App";
import { ReportView } from "../pages/ReportView";

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
});

describe("ReportView", () => {
  it("renders the API-served report full width — the reading column is removed for this view only", async () => {
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
    const doc = frame.getAttribute("srcdoc")!;
    // the report markup is preserved verbatim…
    expect(doc).toContain("<h1>Evaluation report</h1>");
    expect(doc).toContain("max-width: 1400px");
    // …plus exactly ONE injected override style that removes the reading
    // column for this view
    expect(doc).toContain("max-width:none");
    expect(doc.match(/<style>/g)!.length).toBe(2);
    // the view spans the full page width like every other page
    const css = readStylesCss();
    expect(css.match(/\.report-view \{[\s\S]*?\n\}/)![0]).toContain("width: 100%;");
    expect(css.match(/\.report-view \.report-frame \{[\s\S]*?\n\}/)![0]).toContain(
      "width: 100%;",
    );
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
