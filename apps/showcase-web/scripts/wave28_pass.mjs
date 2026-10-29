/* Playwright smoke pass for the forecast workbench after the wave-28 frontend
 * update: renders the demo at its new defaults (28d, all models), fails on any
 * console error, verifies the weekly band rows + fixed verdict scale label in
 * the live DOM, and writes screenshots to artifacts/playwright-m5/. */
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const BASE = "http://127.0.0.1:4321";
const OUT = new URL("../../../artifacts/playwright-m5/", import.meta.url).pathname;
mkdirSync(OUT, { recursive: true });

const errors = [];
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
page.on("console", (msg) => {
  if (msg.type() === "error") errors.push(msg.text());
});
page.on("pageerror", (err) => errors.push(String(err)));

await page.goto(`${BASE}/demos/forecast-workbench`, { waitUntil: "networkidle" });
await page.getByRole("heading", { level: 1, name: "demand forecast workbench" }).waitFor();

// defaults: 28d + every model chip selected
for (const name of ["seasonal naive", "AutoETS", "LightGBM", "lgbm l2", "ensemble", "ensemble l2"]) {
  const pressed = await page.getByRole("button", { name, exact: true }).getAttribute("aria-pressed");
  if (pressed !== "true") throw new Error(`model chip not selected by default: ${name}`);
}
if ((await page.getByRole("button", { name: "28d" }).getAttribute("aria-pressed")) !== "true") {
  throw new Error("horizon 28d is not the default");
}

await page.screenshot({ path: `${OUT}/01-defaults-28d-all-models.png`, fullPage: true });

// band calibration card: weekly rows w1..w4 at h=28
const bandCard = page.getByText("band calibration").locator("..").locator(".figure-card");
const weeks = bandCard.locator(".fwb-band-week");
const weekCount = await weeks.count();
if (weekCount !== 4) throw new Error(`expected 4 weekly rows at h=28, got ${weekCount}`);
for (let i = 0; i < weekCount; i++) {
  const label = await weeks.nth(i).locator(".fwb-band-week-label").textContent();
  const days = await weeks.nth(i).locator(".fwb-band-day").count();
  if (label !== `w${i + 1}` || days !== 7) throw new Error(`bad week row ${i + 1}: ${label}, ${days} days`);
}
await bandCard.screenshot({ path: `${OUT}/02-band-weekly-rows.png` });

// verdict card: fixed common-scale axis label present
const verdictCard = page.getByText("model verdict").locator("..").locator(".figure-card");
const scaleText = await verdictCard.locator(".fwb-verdict-scale").textContent();
if (!/wape@28d scale max 0\.\d{3}/.test(scaleText ?? "")) {
  throw new Error(`verdict scale label missing: ${scaleText}`);
}
// toggling a subset must not move another bar's width (pixel-identical)
const lightgbmFill = verdictCard
  .locator(".fwb-verdict-item", { hasText: "LightGBM" })
  .locator(".fwb-bar-fill");
const widthBefore = await lightgbmFill.evaluate((el) => el.style.width);
await page.getByRole("button", { name: "AutoETS" }).click();
await page.getByRole("button", { name: "ensemble", exact: true }).click();
const widthAfter = await lightgbmFill.evaluate((el) => el.style.width);
if (widthBefore !== widthAfter) throw new Error(`bar width moved: ${widthBefore} -> ${widthAfter}`);
const scaleAfter = await verdictCard.locator(".fwb-verdict-scale").textContent();
if (scaleAfter !== scaleText) throw new Error("scale label changed when toggling models");
await page.getByRole("button", { name: "AutoETS" }).click();
await page.getByRole("button", { name: "ensemble", exact: true }).click();
const restored = await verdictCard.locator(".fwb-verdict-item").count();
if (restored !== 6) throw new Error(`expected 6 verdict rows after restore, got ${restored}`);
await verdictCard.screenshot({ path: `${OUT}/03-verdict-scale-label.png` });

// h=7: single weekly row, squares fill the slot (card keeps its height)
await page.getByRole("button", { name: "7d" }).click();
const weeks7 = await bandCard.locator(".fwb-band-week").count();
if (weeks7 !== 1) throw new Error(`expected 1 weekly row at h=7, got ${weeks7}`);
const stripBox = await bandCard.locator(".fwb-band-weeks").boundingBox();
const cardBox = await bandCard.boundingBox();
if (!stripBox || !cardBox || stripBox.height < cardBox.height * 0.25) {
  throw new Error(`band grid does not fill its slot at h=7: ${JSON.stringify({ stripBox, cardBox })}`);
}
await bandCard.screenshot({ path: `${OUT}/04-band-weekly-rows-h7.png` });
await page.getByRole("button", { name: "28d" }).click();

// h=14: two rows
await page.getByRole("button", { name: "14d" }).click();
if ((await bandCard.locator(".fwb-band-week").count()) !== 2) throw new Error("expected 2 weekly rows at h=14");

await browser.close();

if (errors.length > 0) {
  console.error("CONSOLE ERRORS:\n" + errors.join("\n"));
  process.exit(1);
}
console.log("playwright pass OK — zero console errors");
console.log("scale label:", scaleText);
console.log("screenshots in", OUT);
