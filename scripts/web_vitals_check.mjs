#!/usr/bin/env node
/** Lab Web Vitals smoke for the production shell (not a field-RUM substitute). */
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const require = createRequire(path.join(ROOT, "apps", "showcase-web", "package.json"));
const { chromium } = require("playwright");
const BASE_URL = (process.env.BASE_URL ?? "https://localhost:8443").replace(/\/$/, "");

const browser = await chromium.launch();
try {
  const context = await browser.newContext({ ignoreHTTPSErrors: true });
  const page = await context.newPage();
  await page.addInitScript(() => {
    const vitals = { lcp: 0, cls: 0, inp: 0 };
    Object.assign(window, { __portfolioVitals: vitals });
    new PerformanceObserver((list) => {
      const last = list.getEntries().at(-1);
      if (last) vitals.lcp = last.startTime;
    }).observe({ type: "largest-contentful-paint", buffered: true });
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        if (!entry.hadRecentInput) vitals.cls += entry.value;
      }
    }).observe({ type: "layout-shift", buffered: true });
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        if (["click", "keydown", "pointerdown"].includes(entry.name)) {
          vitals.inp = Math.max(vitals.inp, entry.duration);
        }
      }
    }).observe({ type: "event", buffered: true, durationThreshold: 16 });
  });

  await page.goto(`${BASE_URL}/`, { waitUntil: "networkidle", timeout: 60_000 });
  await page.locator('.nav-links a[href="/projects"]').click();
  await page.waitForURL("**/projects", { timeout: 30_000 });
  await page.waitForTimeout(500);
  const metrics = await page.evaluate(() => window.__portfolioVitals);
  console.log(`web-vitals: ${JSON.stringify(metrics)}`);
  if (metrics.lcp > 2500) throw new Error(`LCP ${metrics.lcp}ms exceeds 2500ms`);
  if (metrics.inp > 200) throw new Error(`INP ${metrics.inp}ms exceeds 200ms`);
  if (metrics.cls > 0.1) throw new Error(`CLS ${metrics.cls} exceeds 0.1`);
  console.log("web-vitals: OK (lab thresholds: LCP 2.5s, INP 200ms, CLS 0.1)");
} finally {
  await browser.close();
}
