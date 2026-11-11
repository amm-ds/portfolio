#!/usr/bin/env node
/** Production-mode CSP smoke against Caddy + the real FastAPI/React image. */
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const require = createRequire(path.join(ROOT, "apps", "showcase-web", "package.json"));
const { chromium } = require("playwright");
const BASE_URL = (process.env.BASE_URL ?? "https://localhost:8443").replace(/\/$/, "");
const API_URL = (process.env.API_URL ?? "http://localhost:8000").replace(/\/$/, "");
const errors = [];
const docResponses = [];

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

const browser = await chromium.launch();
try {
  const context = await browser.newContext({ ignoreHTTPSErrors: true });
  const page = await context.newPage();
  page.on("console", (message) => {
    const text = message.text();
    if (/Content Security Policy|Refused to (?:load|execute|apply)/i.test(text)) {
      errors.push(`${page.url()}: ${text}`);
    }
  });
  page.on("pageerror", (error) => errors.push(`${page.url()}: ${error.message}`));
  page.on("requestfailed", (request) => {
    const failure = request.failure()?.errorText ?? "request failed";
    // Navigating from a report to the next route cancels its remaining CDN
    // requests. That is expected; CSP console violations stay captured above.
    if (failure !== "net::ERR_ABORTED") errors.push(`${request.url()}: ${failure}`);
  });
  page.on("response", (response) => {
    if (response.url().includes("/docs")) {
      docResponses.push({
        url: response.url(),
        status: response.status(),
        contentType: response.headers()["content-type"] ?? "",
      });
    }
  });

  const home = await page.goto(`${BASE_URL}/`, { waitUntil: "networkidle", timeout: 60_000 });
  assert(home?.status() === 200, "SPA root did not return 200");
  const homeCsp = home.headers()["content-security-policy"] ?? "";
  assert(homeCsp.includes("script-src 'self'"), "SPA lost its same-origin script policy");
  assert(!homeCsp.includes("script-src 'self' 'unsafe-inline'"), "SPA allows inline scripts globally");

  const reportResponse = await page.goto(`${BASE_URL}/projects/01-rag-agent/report`, {
    waitUntil: "networkidle",
    timeout: 60_000,
  });
  assert(reportResponse?.status() === 200, "report page did not return 200");
  const reportCsp = reportResponse?.headers()["content-security-policy"] ?? "";
  assert(reportCsp.includes("script-src 'self' 'unsafe-inline'"), "report lost its inline bootstrap exception");
  // The API owns /projects/:id/report and serves raw HTML directly (not the
  // React ReportView route). Require rendered SVG, not just the placeholder div.
  await page.waitForSelector(".plotly-graph-div .main-svg", { timeout: 45_000 });
  console.log("production report: Plotly executed with route-scoped CSP");

  const figureResponse = await page.goto(
    `${BASE_URL}/projects/01-rag-agent/figures/retrieval_funnel`,
    { waitUntil: "networkidle", timeout: 60_000 },
  );
  const figureStatus = figureResponse?.status();
  const figureBody = figureResponse ? await figureResponse.text() : "";
  assert(
    figureStatus === 200,
    `standalone figure returned ${figureStatus ?? "no response"}: ${figureBody.slice(0, 200)}`,
  );
  const figureCsp = figureResponse?.headers()["content-security-policy"] ?? "";
  assert(figureCsp.includes("script-src 'self' 'unsafe-inline'"), "figure lost its inline bootstrap exception");
  await page.waitForSelector(".plotly-graph-div .main-svg", { timeout: 45_000 });
  console.log("production figure: Plotly executed with route-scoped CSP");

  // API docs: the edge intentionally carries NO /docs CSP exception
  // (external audit F-14 removed it — docs are disabled by default and the
  // strict same-origin script policy applies everywhere). Through Caddy, an
  // enabled docs page must arrive WITHOUT the inline exception, and the
  // strict policy must actively refuse Swagger's inline bootstrap; the
  // opt-in docs path is verified direct against the API container, where no
  // edge CSP is injected.
  const docsEdge = await page.goto(`${BASE_URL}/docs`, {
    waitUntil: "networkidle",
    timeout: 60_000,
  });
  assert(docsEdge?.status() === 200, "FastAPI docs did not return 200 through the edge");
  const docsEdgeCsp = docsEdge?.headers()["content-security-policy"] ?? "";
  assert(
    docsEdgeCsp.includes("script-src 'self'") && !docsEdgeCsp.includes("'unsafe-inline'"),
    "edge granted the docs inline-script exception (F-14 regression)",
  );
  const edgeRefusals = errors.length;
  assert(edgeRefusals > 0, "edge docs page raised no CSP refusal — the strict policy is gone");
  errors.length = 0;
  console.log("production docs: edge keeps the strict same-origin script policy");

  const apiDocs = await page.goto(`${API_URL}/docs`, {
    waitUntil: "networkidle",
    timeout: 60_000,
  });
  assert(apiDocs?.status() === 200, "FastAPI docs did not return 200 on the API container");
  try {
    await page.waitForSelector(".swagger-ui .information-container", { timeout: 45_000 });
  } catch (error) {
    const diagnostics = await page.evaluate(() => ({
      body: document.body.innerText.slice(0, 300),
      scripts: [...document.scripts].map((script) => script.src || "inline"),
      resources: performance
        .getEntriesByType("resource")
        .map((entry) => entry.name)
        .filter((name) => name.includes("/docs") || name.includes("cdn.")),
    }));
    console.error(
      "Swagger diagnostics:",
      JSON.stringify({ ...diagnostics, docResponses, errors: errors.map((error) => error.slice(0, 500)) }),
    );
    throw error;
  }
  console.log("production docs: Swagger UI executes on the opt-in API path");

  assert(errors.length === 0, `CSP/browser errors:\n${errors.join("\n")}`);
  console.log("production-smoke: OK");
} finally {
  await browser.close();
}
