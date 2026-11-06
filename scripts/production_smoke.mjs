#!/usr/bin/env node
/** Production-mode CSP smoke against Caddy + the real FastAPI/React image. */
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const require = createRequire(path.join(ROOT, "apps", "showcase-web", "package.json"));
const { chromium } = require("playwright");
const BASE_URL = (process.env.BASE_URL ?? "https://localhost:8443").replace(/\/$/, "");
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
    errors.push(`${request.url()}: ${request.failure()?.errorText ?? "request failed"}`);
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
  // The API owns /projects/:id/report and serves raw HTML directly (not the
  // React ReportView route). Validate that real production path.
  await page.waitForSelector(".plotly-graph-div", { timeout: 45_000 });
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
  await page.waitForSelector(".plotly-graph-div", { timeout: 45_000 });
  console.log("production figure: Plotly executed with route-scoped CSP");

  const docsResponse = await page.goto(`${BASE_URL}/docs`, {
    waitUntil: "networkidle",
    timeout: 60_000,
  });
  assert(docsResponse?.status() === 200, "FastAPI docs did not return 200");
  try {
    await page.waitForSelector(".swagger-ui", { timeout: 45_000 });
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
  console.log("production docs: Swagger UI executed");

  assert(errors.length === 0, `CSP/browser errors:\n${errors.join("\n")}`);
  console.log("production-smoke: OK");
} finally {
  await browser.close();
}
