// Pre-render every ```mermaid block found in projects/*/story.yaml to a
// static SVG in public/diagrams/<sha1(code)>.svg, so the site never depends
// on runtime mermaid.render (which fails in Safari). Run locally:
//
//   node apps/showcase-web/scripts/render-diagrams.mjs
//
// playwright is borrowed from a sibling checkout (not a dependency of this
// app): set PLAYWRIGHT_MODULE to override the default path below.
import { createRequire } from "node:module";
import { createHash } from "node:crypto";
import { mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const webRoot = path.resolve(here, "..");
const repoRoot = path.resolve(webRoot, "../..");
const projectsDir = path.join(repoRoot, "projects");
const outDir = path.join(webRoot, "public", "diagrams");
const mermaidDist = path.join(webRoot, "node_modules", "mermaid", "dist", "mermaid.min.js");
const themeFile = path.join(webRoot, "src", "components", "mermaid-theme.ts");

const require = createRequire(
  process.env.PLAYWRIGHT_MODULE ??
    "/Users/alejandro/work/crypto_market_dashboard/node_modules/playwright",
);
const { chromium } = require("playwright");

// --- MERMAID_THEME: read the shared theme file and eval its object literal.
// Strips TS `as const` annotations; keeps script and component in lockstep.
const themeSource = await readFile(themeFile, "utf8");
const themeMatch = themeSource.match(/export const MERMAID_THEME = (\{[\s\S]*?\n\});/);
if (!themeMatch) throw new Error(`could not parse MERMAID_THEME from ${themeFile}`);
const MERMAID_THEME = eval(`(${themeMatch[1].replace(/ as const/g, "")})`);

// --- Extract mermaid blocks from raw story.yaml text. Two encodings appear
// in the corpus:
//  a) double-quoted YAML scalars: the fence is embedded as literal
//     "\`\`\`mermaid\n...\n\`\`\`" (backslash-n escapes) on one physical line.
//  b) block scalars (|): real newlines; the fence sits on its own line and
//     YAML strips the block indent, which equals the fence indent.
// Both passes reproduce exactly the string markdown.tsx later hands to
// MermaidDiagram (fence content lines joined with "\n", dedented).
function unescapeYamlDoubleQuoted(s) {
  return s.replace(/\\(.)/g, (m, c) => {
    const map = { n: "\n", t: "\t", r: "\r", '"': '"', "\\": "\\", "/": "/", "0": "\0" };
    return c in map ? map[c] : m;
  });
}

function extractMermaidBlocks(raw) {
  const blocks = [];
  // (a) escaped fences inside double-quoted scalars
  for (const m of raw.matchAll(/```mermaid\\n([\s\S]*?)\\n```/g)) {
    blocks.push(unescapeYamlDoubleQuoted(m[1]));
  }
  // (b) block scalars: fence on its own line
  const lines = raw.split("\n");
  for (let i = 0; i < lines.length; i += 1) {
    const open = lines[i].match(/^(\s*)```mermaid\s*$/);
    if (!open) continue;
    const indent = open[1].length;
    const codeLines = [];
    i += 1;
    while (i < lines.length && !/^\s*```\s*$/.test(lines[i])) {
      const line = lines[i];
      const strip = Math.min(indent, line.match(/^ */)[0].length);
      codeLines.push(line.slice(strip));
      i += 1;
    }
    if (i >= lines.length) throw new Error(`unclosed mermaid fence near line ${i} of story.yaml`);
    blocks.push(codeLines.join("\n"));
  }
  return blocks;
}

// --- Collect blocks across projects, keeping document order, deduped by code.
const entries = []; // { project, code, hash }
const seen = new Set();
const projectDirs = (await readdir(projectsDir, { withFileTypes: true }))
  .filter((d) => d.isDirectory() && /^\d{2}-/.test(d.name))
  .map((d) => d.name)
  .sort();
for (const project of projectDirs) {
  const story = path.join(projectsDir, project, "story.yaml");
  let raw;
  try {
    raw = await readFile(story, "utf8");
  } catch {
    continue; // project without a story
  }
  for (const code of extractMermaidBlocks(raw)) {
    if (seen.has(code)) continue;
    seen.add(code);
    entries.push({ project, code, hash: createHash("sha1").update(code).digest("hex") });
  }
}

console.log(`extracted ${entries.length} unique mermaid diagrams from ${projectDirs.length} projects`);

// --- Render each block in headless Chromium via the standalone mermaid dist.
await mkdir(outDir, { recursive: true });
const browser = await chromium.launch();
try {
  const page = await browser.newPage();
  await page.goto("about:blank");
  await page.addScriptTag({ path: mermaidDist });
  await page.evaluate((theme) => {
    window.mermaid.initialize(theme);
  }, MERMAID_THEME);

  const failures = [];
  let totalBytes = 0;
  for (const [i, entry] of entries.entries()) {
    let svg;
    try {
      svg = await page.evaluate(
        async ({ id, code }) => {
          const { svg } = await window.mermaid.render(id, code);
          return svg;
        },
        { id: `mmd-${i}`, code: entry.code },
      );
    } catch (err) {
      failures.push({ entry, err });
      console.error(`FAIL ${entry.project} ${entry.hash}: ${err.message}`);
      continue;
    }
    const file = path.join(outDir, `${entry.hash}.svg`);
    let skipped = false;
    try {
      skipped = (await readFile(file, "utf8")) === svg;
    } catch {
      skipped = false;
    }
    if (!skipped) await writeFile(file, svg, "utf8");
    totalBytes += Buffer.byteLength(svg);
    console.log(
      `${entry.project}  ${entry.hash}  ${Buffer.byteLength(svg)} bytes${skipped ? "  (unchanged)" : ""}`,
    );
  }

  if (failures.length > 0) {
    console.error(`\n${failures.length} diagram(s) failed to render:`);
    for (const { entry, err } of failures) {
      console.error(`--- ${entry.project} ${entry.hash}\n${entry.code}\n>>> ${err.message}`);
    }
    process.exitCode = 1;
  } else {
    console.log(`\nrendered ${entries.length} diagrams, ${totalBytes} total bytes -> ${outDir}`);
  }
} finally {
  await browser.close();
}
