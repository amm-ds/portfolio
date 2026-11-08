// Pre-render every ```mermaid block found in projects/*/story.yaml to
// dark and light static SVGs in public/diagrams/<sha1(code)>.<theme>.svg, so
// the site never depends on runtime mermaid.render (which fails in Safari). Run locally:
//
//   node apps/showcase-web/scripts/render-diagrams.mjs
//
// Playwright is a declared development dependency of this app.
import { createRequire } from "node:module";
import { createHash } from "node:crypto";
import { mkdir, readFile, readdir, unlink, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const webRoot = path.resolve(here, "..");
const repoRoot = path.resolve(webRoot, "../..");
const projectsDir = path.join(repoRoot, "projects");
const outDir = path.join(webRoot, "public", "diagrams");
const mermaidDist = path.join(webRoot, "node_modules", "mermaid", "dist", "mermaid.min.js");
const themeFile = path.join(webRoot, "src", "components", "mermaid-theme.ts");

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

// --- MERMAID_THEMES: read the shared theme map and eval its object literal.
// Strips TS `as const` annotations; keeps script and component in lockstep.
const themeSource = await readFile(themeFile, "utf8");
const themeMatch = themeSource.match(/export const MERMAID_THEMES = (\{[\s\S]*?\n\}\s*as const);/);
if (!themeMatch) throw new Error(`could not parse MERMAID_THEMES from ${themeFile}`);
const MERMAID_THEMES = eval(`(${themeMatch[1].replace(/ as const/g, "")})`);
const DIAGRAM_THEMES = ["dark", "light"];

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
  // (b) native TS template literals: the opening fence can follow `const X =`.
  for (const m of raw.matchAll(/```mermaid\n([\s\S]*?)\n```/g)) {
    blocks.push(m[1]);
  }
  // (c) YAML block scalars: fence on its own line
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

// Native app articles use the same fenced-code contract and static fallback.
const appArticles = ["AgentChatArticle.tsx", "DocumentIntelligenceArticle.tsx"];
for (const article of appArticles) {
  const source = (
    await readFile(path.join(webRoot, "src", "pages", article), "utf8")
  ).replaceAll("\\`", "`");
  for (const code of extractMermaidBlocks(source)) {
    if (seen.has(code)) continue;
    seen.add(code);
    entries.push({
      project: `apps/${article.replace("Article.tsx", "").replace(/([a-z])([A-Z])/g, "$1-$2").toLowerCase()}`,
      code,
      hash: createHash("sha1").update(code).digest("hex"),
    });
  }
}

console.log(`extracted ${entries.length} unique mermaid diagrams from ${projectDirs.length} projects + app articles`);

// --- Report generated files whose source fence no longer exists. Pruning is
// explicit so a normal render never deletes artifacts as a side effect.
await mkdir(outDir, { recursive: true });
const expectedFiles = new Set(
  entries.flatMap((entry) => DIAGRAM_THEMES.map((theme) => `${entry.hash}.${theme}.svg`)),
);
const staleFiles = (await readdir(outDir))
  .filter((file) => file.endsWith(".svg") && !expectedFiles.has(file))
  .sort();
if (staleFiles.length > 0) {
  console.log(`stale SVGs: ${staleFiles.join(", ")}`);
  if (process.argv.includes("--prune")) {
    await Promise.all(staleFiles.map((file) => unlink(path.join(outDir, file))));
    console.log(`pruned ${staleFiles.length} stale SVGs`);
  } else {
    console.log("rerun with --prune to delete only these stale SVGs");
  }
}

// --- Render each block in both supported themes via headless Chromium and the
// standalone mermaid dist.
const browser = await chromium.launch();
try {
  const page = await browser.newPage();
  await page.goto("about:blank");
  await page.addScriptTag({ path: mermaidDist });

  const failures = [];
  let rendered = 0;
  let totalBytes = 0;
  for (const theme of DIAGRAM_THEMES) {
    await page.evaluate((config) => {
      window.mermaid.initialize(config);
    }, MERMAID_THEMES[theme]);
    for (const [i, entry] of entries.entries()) {
      let svg;
      try {
        svg = await page.evaluate(
          async ({ id, code }) => {
            const { svg } = await window.mermaid.render(id, code);
            return svg;
          },
          { id: `mmd-${i}-${theme}`, code: entry.code },
        );
      } catch (err) {
        failures.push({ entry, theme, err });
        console.error(`FAIL ${entry.project} ${entry.hash}.${theme}: ${err.message}`);
        continue;
      }
      const file = path.join(outDir, `${entry.hash}.${theme}.svg`);
      let skipped = false;
      try {
        skipped = (await readFile(file, "utf8")) === svg;
      } catch {
        skipped = false;
      }
      if (!skipped) await writeFile(file, svg, "utf8");
      rendered += 1;
      totalBytes += Buffer.byteLength(svg);
      console.log(
        `${entry.project}  ${entry.hash}.${theme}  ${Buffer.byteLength(svg)} bytes${skipped ? "  (unchanged)" : ""}`,
      );
    }
  }

  if (failures.length > 0) {
    console.error(`\n${failures.length} diagram theme variant(s) failed to render:`);
    for (const { entry, theme, err } of failures) {
      console.error(`--- ${entry.project} ${entry.hash}.${theme}\n${entry.code}\n>>> ${err.message}`);
    }
    process.exitCode = 1;
  } else {
    console.log(`\nrendered ${rendered} diagram variants, ${totalBytes} total bytes -> ${outDir}`);
  }
} finally {
  await browser.close();
}
