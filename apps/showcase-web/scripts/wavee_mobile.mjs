/* Wave-E mobile pass: screenshots the demo workbenches (bottom cards), the
 * projects index, the home page, and a story page at 390×844 in webkit (with
 * chromium for comparison). Usage: node scripts/wavee_mobile.mjs [before|after]
 * — writes to artifacts/wave-e-mobile/<phase>-*.png and fails on console errors. */
import { chromium, webkit } from "playwright";
import { mkdirSync } from "node:fs";

const BASE = "http://127.0.0.1:4321";
const phase = process.argv[2] ?? "before";
const OUT = new URL("../../../artifacts/wave-e-mobile/", import.meta.url).pathname;
mkdirSync(OUT, { recursive: true });

const PAGES = [
  { name: "churn-sandbox", path: "/demos/churn-sandbox", band: true },
  { name: "forecast-workbench", path: "/demos/forecast-workbench", band: true },
  { name: "projects-index", path: "/projects", band: false },
  { name: "home", path: "/", band: false },
  { name: "story-churn", path: "/projects/05-ml-pipeline-churn", band: false },
];

const errors = [];

for (const engine of ["webkit", "chromium"]) {
  const browser = await (engine === "webkit" ? webkit : chromium).launch();
  const page = await browser.newPage({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 2,
  });
  page.on("console", (msg) => {
    if (msg.type() === "error") errors.push(`${engine}: ${msg.text()}`);
  });
  page.on("pageerror", (err) => errors.push(`${engine}: ${err}`));

  for (const p of PAGES) {
    await page.goto(`${BASE}${p.path}`, { waitUntil: "networkidle" });
    await page.waitForTimeout(400);
    await page.screenshot({ path: `${OUT}/${phase}-${engine}-${p.name}.png`, fullPage: true });
    if (p.band) {
      // the band keeps reflowing on mobile (the bug under investigation), so a
      // clip shot from its bounding box — element shots wait for stability
      await page.evaluate(() => {
        document.querySelector(".wb-secondary")?.scrollIntoView({ block: "start" });
      });
      await page.waitForTimeout(300);
      const clip = await page.evaluate(() => {
        const el = document.querySelector(".wb-secondary");
        if (!el) return null;
        const r = el.getBoundingClientRect();
        const h = Math.min(r.height, window.innerHeight - r.y);
        return h > 0 ? { x: r.x, y: Math.max(r.y, 0), width: r.width, height: h } : null;
      });
      if (clip) {
        await page.screenshot({ path: `${OUT}/${phase}-${engine}-${p.name}-band.png`, clip });
      }
    }
    console.log(`${phase} ${engine}: ${p.path} OK`);
  }
  await browser.close();
}

if (errors.length > 0) {
  console.error("CONSOLE ERRORS:\n" + errors.join("\n"));
  process.exit(1);
}
console.log(`screenshots in ${OUT}`);
