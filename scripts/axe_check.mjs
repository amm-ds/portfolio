#!/usr/bin/env node
/**
 * axe_check.mjs — accessibility smoke test for the showcase SPA.
 *
 * Visits core routes at desktop/tablet/mobile widths on the Vite dev server,
 * runs axe-core on each page, writes the full results to reports/axe.json,
 * and exits non-zero when any violation is found.
 *
 * Usage (dev server must be running):
 *   node scripts/axe_check.mjs
 *   AXE_BASE_URL=http://127.0.0.1:4321 node scripts/axe_check.mjs
 *
 * The script resolves @axe-core/playwright and playwright from
 * apps/showcase-web (where they are devDependencies), so it can live at the
 * repo root and still run from a checkout without a root package.json.
 */
import { createRequire } from "node:module";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const WEB_DIR = path.join(ROOT, "apps", "showcase-web");
// Resolve the dev deps from the web app regardless of the caller's cwd.
const require = createRequire(path.join(WEB_DIR, "package.json"));
const { chromium } = require("playwright");
const { AxeBuilder } = require("@axe-core/playwright");

const BASE_URL = (process.env.AXE_BASE_URL ?? "http://127.0.0.1:4321").replace(/\/$/, "");
const ROUTES = [
  "/",
  "/projects",
  "/projects/04-nlp-classification",
  "/projects/05-ml-pipeline-churn",
  "/projects/09-agentic-workflows",
  "/projects/01-rag-agent/report",
  "/apps/agent-chat",
  "/apps/document-intelligence",
  "/glossary",
  "/contact",
  "/demos/churn-sandbox",
  "/demos/forecast-workbench",
];
const VIEWPORTS = [
  { name: "desktop", width: 1440, height: 1100 },
  { name: "tablet", width: 768, height: 1024 },
  { name: "mobile", width: 390, height: 844 },
];
const REPORT_PATH = path.join(ROOT, "reports", "axe.json");

async function main() {
  const browser = await chromium.launch();
  const themes = [
    { name: "dark", storageValue: "dark" },
    { name: "light", storageValue: "light" },
  ];
  try {
    const results = [];

    for (const theme of themes) {
      for (const viewport of VIEWPORTS) {
        // A fresh context per theme/viewport isolates storage and gives AxeBuilder
        // the explicit context it requires.
        const context = await browser.newContext({
          viewport: { width: viewport.width, height: viewport.height },
        });
        await context.addInitScript(
          ([key, value]) => window.localStorage.setItem(key, value),
          ["portfolio-theme", theme.storageValue],
        );
        const page = await context.newPage();
        try {
          for (const route of ROUTES) {
            const url = `${BASE_URL}${route}`;
            let httpStatus = null;
            if (route.endsWith("/report")) {
              // In dev, /projects/* is proxied to the API for direct navigations.
              // Open the SPA case study first, then navigate client-side so the
              // routed ReportView frame (not the raw API HTML) is scanned.
              const parentRoute = route.slice(0, -"/report".length);
              const parentResponse = await page.goto(`${BASE_URL}${parentRoute}`, {
                waitUntil: "networkidle",
                timeout: 30_000,
              });
              httpStatus = parentResponse?.status() ?? null;
              const reportLink = page.locator(`a[href="${route}"]`).first();
              await reportLink.waitFor({ state: "visible", timeout: 30_000 });
              await reportLink.click();
              await page.locator(".report-frame").waitFor({ state: "attached", timeout: 30_000 });
            } else {
              const response = await page.goto(url, { waitUntil: "networkidle", timeout: 30_000 });
              httpStatus = response?.status() ?? null;
            }
            // Let lazy charts/figures settle before scanning.
            await page.waitForTimeout(500);

            const analysis = await new AxeBuilder({ page }).analyze();
            const failing = analysis.violations;
            results.push({
              theme: theme.name,
              route,
              viewport: viewport.name,
              url,
              httpStatus,
              passes: analysis.passes.length,
              violationCount: analysis.violations.length,
              failingViolations: failing.map((v) => ({
                id: v.id,
                impact: v.impact,
                help: v.help,
                helpUrl: v.helpUrl,
                nodes: v.nodes.map((n) => n.target),
              })),
              violations: analysis.violations.map((v) => ({
                id: v.id,
                impact: v.impact,
                help: v.help,
                helpUrl: v.helpUrl,
                nodes: v.nodes.map((n) => ({ target: n.target, failureSummary: n.failureSummary })),
              })),
            });
            console.log(
              `[axe] ${theme.name} ${viewport.name} ${route} — http ${httpStatus}, ` +
                `${analysis.passes.length} passes, ${analysis.violations.length} violations`,
            );
          }
        } finally {
          await context.close();
        }
      }
    }

    await mkdir(path.dirname(REPORT_PATH), { recursive: true });
    await writeFile(REPORT_PATH, JSON.stringify({ baseUrl: BASE_URL, results }, null, 2));
    console.log(`[axe] report written to ${path.relative(ROOT, REPORT_PATH)}`);

    const httpFailures = results
      .filter((r) => r.httpStatus !== 200)
      .map(
        (r) =>
          `${r.theme} ${r.viewport} ${r.route}: HTTP ${r.httpStatus ?? "no response"}`,
      );
    const failures = [
      ...httpFailures,
      ...results.flatMap((r) =>
        r.failingViolations.map(
          (v) => `${r.theme} ${r.viewport} ${r.route}: [${v.impact}] ${v.id} — ${v.help}`,
        ),
      ),
    ];
    if (failures.length > 0) {
      console.error(`[axe] FAIL — ${failures.length} violation(s):`);
      for (const f of failures) console.error(`  ${f}`);
      process.exitCode = 1;
    } else {
      console.log("[axe] OK — no violations in dark or light at desktop, tablet, or mobile widths");
    }
  } finally {
    await browser.close();
  }
}

main().catch((err) => {
  console.error("[axe] error:", err);
  process.exitCode = 1;
});
