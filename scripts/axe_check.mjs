#!/usr/bin/env node
/**
 * axe_check.mjs — accessibility smoke test for the showcase SPA.
 *
 * Visits the core routes on the Vite dev server with headless Chromium,
 * runs axe-core on each page, writes the full results to reports/axe.json,
 * and exits non-zero when any serious/critical violation is found.
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
  "/projects/05-ml-pipeline-churn",
  "/demos/churn-sandbox",
  "/demos/forecast-workbench",
];
/** Violation impacts that fail the check. */
const FAILING_IMPACTS = new Set(["critical", "serious"]);
const REPORT_PATH = path.join(ROOT, "reports", "axe.json");

async function main() {
  const browser = await chromium.launch();
  try {
    // AxeBuilder requires a page from an explicit context (browser.newPage()
    // is not supported).
    const context = await browser.newContext();
    const page = await context.newPage();
    const results = [];

    for (const route of ROUTES) {
      const url = `${BASE_URL}${route}`;
      const response = await page.goto(url, { waitUntil: "networkidle", timeout: 30_000 });
      const httpStatus = response?.status() ?? null;
      // Let lazy charts/figures settle before scanning.
      await page.waitForTimeout(500);

      const analysis = await new AxeBuilder({ page }).analyze();
      const failing = analysis.violations.filter((v) => FAILING_IMPACTS.has(v.impact));
      results.push({
        route,
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
        // Full detail for the report: every violation (any impact) with nodes.
        violations: analysis.violations.map((v) => ({
          id: v.id,
          impact: v.impact,
          help: v.help,
          helpUrl: v.helpUrl,
          nodes: v.nodes.map((n) => ({ target: n.target, failureSummary: n.failureSummary })),
        })),
      });
      console.log(
        `[axe] ${route} — http ${httpStatus}, ${analysis.passes.length} passes, ` +
          `${analysis.violations.length} violations (${failing.length} serious/critical)`,
      );
    }

    await mkdir(path.dirname(REPORT_PATH), { recursive: true });
    await writeFile(REPORT_PATH, JSON.stringify({ baseUrl: BASE_URL, results }, null, 2));
    console.log(`[axe] report written to ${path.relative(ROOT, REPORT_PATH)}`);

    const failures = results.flatMap((r) =>
      r.failingViolations.map((v) => `${r.route}: [${v.impact}] ${v.id} — ${v.help}`),
    );
    if (failures.length > 0) {
      console.error(`[axe] FAIL — ${failures.length} serious/critical violation(s):`);
      for (const f of failures) console.error(`  ${f}`);
      process.exitCode = 1;
    } else {
      console.log("[axe] OK — no serious or critical violations");
    }
  } finally {
    await browser.close();
  }
}

main().catch((err) => {
  console.error("[axe] error:", err);
  process.exitCode = 1;
});
