#!/usr/bin/env node
/** Real-browser React Flow regression gate. Run the Vite dev server first:
 * node scripts/check_flow_diagrams.mjs
 * FLOW_BASE_URL and FLOW_ENGINES=chromium,webkit are optional. */
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { chromium, webkit } = require("playwright");
const { AxeBuilder } = require("@axe-core/playwright");
const BASE_URL = (process.env.FLOW_BASE_URL ?? "http://127.0.0.1:4321").replace(/\/$/, "");
const engines = (process.env.FLOW_ENGINES ?? "chromium,webkit").split(",");
const routes = ["/projects/09-agentic-workflows", "/projects/01-rag-agent"];
const widths = [390, 768, 1440];
const failures = [];

function check(condition, message) {
  if (!condition) failures.push(message);
}

async function checkGeometry(diagram, name) {
  const result = await diagram.evaluate((root) => {
    const canvas = root.querySelector(".flow-diagram__canvas");
    const viewport = root.querySelector(".react-flow__viewport");
    if (!canvas || !viewport) return { error: "missing canvas/viewport" };
    const canvasRect = canvas.getBoundingClientRect();
    const nodes = [...root.querySelectorAll(".react-flow__node")].map((element) => ({
      id: element.dataset.id,
      name: element.getAttribute("aria-label") ?? element.textContent,
      rect: element.getBoundingClientRect(),
    }));
    const labels = [...root.querySelectorAll(".flow-edge__label")].map((element) => ({
      name: element.textContent,
      rect: element.getBoundingClientRect(),
    }));
    const contained = [...nodes, ...labels].flatMap(({ name, rect }) =>
      rect.left < canvasRect.left - 3 || rect.top < canvasRect.top - 3 ||
      rect.right > canvasRect.right + 3 || rect.bottom > canvasRect.bottom + 3
        ? [`clipped: ${name}`]
        : [],
    );
    const overlap = (a, b, padding = 2) =>
      Math.min(a.right, b.right) - Math.max(a.left, b.left) > padding &&
      Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > padding;
    const labelOverlaps = [];
    for (let i = 0; i < labels.length; i++) {
      for (let j = i + 1; j < labels.length; j++) {
        if (overlap(labels[i].rect, labels[j].rect)) {
          labelOverlaps.push(`${labels[i].name} / ${labels[j].name}`);
        }
      }
    }
    const labelNodeOverlaps = labels.flatMap((label) =>
      nodes.filter((node) => overlap(label.rect, node.rect)).map((node) => `${label.name} / ${node.name}`),
    );
    const edgeNodeOverlaps = [];
    for (const path of root.querySelectorAll(".flow-edge__path")) {
      const matrix = path.getScreenCTM();
      if (!matrix) continue;
      const length = path.getTotalLength();
      for (let step = 4; step < 37; step++) {
        // The first/last 10% intentionally meet their own node boundaries.
        const point = new DOMPoint();
        const local = path.getPointAtLength((length * step) / 40);
        point.x = local.x;
        point.y = local.y;
        const screen = point.matrixTransform(matrix);
        const hit = nodes.find(({ id, rect }) =>
          id !== path.dataset.source && id !== path.dataset.target &&
          screen.x > rect.left + 3 && screen.x < rect.right - 3 &&
          screen.y > rect.top + 3 && screen.y < rect.bottom - 3,
        );
        if (hit) {
          edgeNodeOverlaps.push(`${path.id} / ${hit.name}`);
          break;
        }
      }
    }
    return { contained, labelOverlaps, labelNodeOverlaps, edgeNodeOverlaps };
  });
  check(!result.error, `${name}: ${result.error}`);
  for (const key of ["contained", "labelOverlaps", "labelNodeOverlaps", "edgeNodeOverlaps"]) {
    for (const detail of result[key] ?? []) failures.push(`${name}: ${key}: ${detail}`);
  }
}

for (const engineName of engines) {
  const browser = await (engineName === "webkit" ? webkit : chromium).launch();
  try {
    for (const theme of ["dark", "light"]) {
      for (const width of widths) {
        const context = await browser.newContext({ viewport: { width, height: 900 } });
        await context.addInitScript((value) => localStorage.setItem("portfolio-theme", value), theme);
        const page = await context.newPage();
        page.on("pageerror", (error) => failures.push(`${engineName}/${theme}/${width}: ${error.message}`));
        try {
          for (const route of routes) {
            const name = `${engineName}/${theme}/${width}${route}`;
            await page.goto(`${BASE_URL}${route}`, { waitUntil: "networkidle", timeout: 30_000 });
            const diagrams = page.locator(".flow-diagram");
            check(await diagrams.count() > 0, `${name}: no diagrams`);
            for (let index = 0; index < await diagrams.count(); index++) {
              const diagram = diagrams.nth(index);
              if (!(await diagram.isVisible())) continue;
              await diagram.evaluate((element) => element.scrollIntoView({ block: "center" }));
              // Earlier auto-sized canvases can move this target after the
              // first scroll; re-align once before waiting for intersection.
              await page.waitForTimeout(100);
              await diagram.evaluate((element) => element.scrollIntoView({ block: "center" }));
              await diagram.locator(".frame-skeleton").waitFor({ state: "detached", timeout: 30_000 });
              if (width === 390) {
                const sizes = await diagram.evaluate((root) => {
                  const viewport = root.querySelector(".react-flow__viewport");
                  const zoom = new DOMMatrixReadOnly(getComputedStyle(viewport).transform).m22;
                  return [...root.querySelectorAll(".flow-node__label, .flow-edge__label")].map(
                    (label) => Number.parseFloat(getComputedStyle(label).fontSize) * zoom,
                  );
                });
                check(sizes.every((size) => size >= 11.9), `${name}: mobile label below 12px: ${Math.min(...sizes)}`);
                if (index === 0) {
                  const viewport = diagram.locator(".react-flow__viewport");
                  const before = await viewport.getAttribute("style");
                  const scrollY = await page.evaluate(() => window.scrollY);
                  const box = await diagram.locator(".flow-diagram__canvas").boundingBox();
                  if (box) await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
                  await page.mouse.wheel(0, 160);
                  await page.waitForTimeout(80);
                  check(await page.evaluate(() => window.scrollY) > scrollY, `${name}: canvas captured article scroll`);
                  check(await viewport.getAttribute("style") === before, `${name}: wheel zoomed despite scroll-only gesture`);
                }
              }
            }
            // Scan the readable initial state, before intentionally fitting a
            // dense overview with smaller hit targets.
            const axe = await new AxeBuilder({ page })
              .include(".flow-diagram")
              .options({ rules: { "target-size": { enabled: true } } })
              .analyze();
            for (const violation of axe.violations) {
              failures.push(`${name}: axe ${violation.id}: ${violation.nodes.map((node) => node.target).join(", ")}`);
            }
            for (let index = 0; index < await diagrams.count(); index++) {
              const diagram = diagrams.nth(index);
              if (!(await diagram.isVisible())) continue;
              await diagram.getByRole("button", { name: /fit view/i }).click();
              await page.waitForTimeout(80);
              await checkGeometry(diagram, `${name} diagram ${index + 1}`);
            }

            const interactive = diagrams.first();
            const plan = interactive.getByTestId("rf__node-plan");
            if (route.startsWith("/projects/09")) {
              await plan.focus();
              await plan.press("Enter");
              await interactive.locator(".flow-inspector").waitFor({ state: "visible", timeout: 1000 }).catch(() => {});
              check(await interactive.locator(".flow-inspector").isVisible(), `${name}: Enter did not inspect`);
              await plan.press("Escape");
              await page.waitForTimeout(30);
              check(await interactive.locator(".flow-inspector").count() === 0, `${name}: Escape did not close`);
              await plan.press("Space");
              await interactive.locator(".flow-inspector").waitFor({ state: "visible", timeout: 1000 }).catch(() => {});
              check(await interactive.locator(".flow-inspector").isVisible(), `${name}: Space did not inspect`);
              await plan.press("Escape");
              await plan.hover();
              check(
                await interactive.locator(".flow-edge__label.is-lit").count() > 0,
                `${name}: portaled label not lit`,
              );
              const viewport = interactive.locator(".react-flow__viewport");
              const beforePan = await viewport.getAttribute("style");
              const canvasBox = await interactive.locator(".flow-diagram__canvas").boundingBox();
              if (canvasBox) {
                await page.mouse.move(canvasBox.x + 20, canvasBox.y + 20);
                await page.mouse.down();
                await page.mouse.move(canvasBox.x + 80, canvasBox.y + 50, { steps: 4 });
                await page.mouse.up();
                await page.waitForTimeout(80);
              }
              check(await viewport.getAttribute("style") !== beforePan, `${name}: drag did not pan`);
              await interactive.getByRole("button", { name: /zoom in/i }).click();
              await page.waitForTimeout(80);
              const adjusted = await viewport.getAttribute("style");
              await page.setViewportSize({ width: width === 390 ? 768 : 390, height: 900 });
              await page.waitForTimeout(120);
              check(await viewport.getAttribute("style") === adjusted, `${name}: resize reset user viewport`);
              await page.setViewportSize({ width, height: 900 });
              await page.waitForTimeout(80);
            }
            console.log(`[flow] ${name}: ${await diagrams.count()} diagrams checked`);
          }
        } finally {
          await context.close();
        }
      }
    }
  } finally {
    await browser.close();
  }
}

if (failures.length > 0) {
  console.error(`[flow] FAIL (${failures.length})\n${failures.join("\n")}`);
  process.exitCode = 1;
} else {
  console.log("[flow] OK");
}
