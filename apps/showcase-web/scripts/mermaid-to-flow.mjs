#!/usr/bin/env node
// mermaid-to-flow.mjs — dev-time converter: story ```mermaid fences → React Flow
// DiagramSpec files under src/diagrams/auto/ + ```diagram fence rewrites.
//
// Why this exists: mermaid v12 renders node labels as HTML inside
// <foreignObject> (htmlLabels was removed), and WebKit/Safari mis-paints
// foreignObject content whenever document styles are present at SVG parse
// time — labels collapse onto the first node. React Flow diagrams render
// correctly on desktop, mobile, and WebKit, so the whole corpus moves over.
//
// What it does (run from anywhere, e.g. `node scripts/mermaid-to-flow.mjs`):
//   1. Scans ../../projects/<NN-*>/story.yaml for ```mermaid fences, in file
//      order. Each block becomes spec id `auto-<project>-<n>` (n = 1-based
//      position among that file's mermaid blocks) and file
//      src/diagrams/auto/<project>-<n>.ts. The fence is replaced in place with
//      ```diagram auto-<project>-<n>``` (same indentation). After a successful
//      rewrite there are no mermaid fences left, so a re-run regenerates
//      nothing. Stale spec files are not pruned, and inserting a block
//      mid-file renumbers later ids — append rather than insert.
//   2. Extracts the one ```mermaid template literal from each app article TSX
//      (src/pages/{AgentChatArticle,DocumentIntelligenceArticle}.tsx) and emits
//      specs the same way (auto-app-agent-chat-1, auto-app-document-intelligence-1).
//      Once the article embeds land, the constants are gone and this step
//      warns and skips — those specs are committed artifacts by then.
//   3. Regenerates src/diagrams/auto/index.ts (alphabetical spec registry).
//
// Parser coverage is exactly the corpus subset: `graph|flowchart LR|TB`,
// nodes [rect]→tool, (stadium)→source/output, {rhombus}→gate, [(cylinder)]→data,
// [[subroutine]]→agent; edges `-->` (task), `---` and `-.->` (result), labels
// via -->|"…"|, -->|…|, -.->|…|, or -- text -->; subgraph NAME["label"] … end
// (flattened: member ids prefixed with the subgraph slug, the subgraph label
// noted on the first member's label, and subgraph-to-subgraph edges resolved
// exit→entry: source exits to target entries; a subgraph without internal
// edges uses all its members). Node labels are single-line: <br/> becomes
// " · ". Auto specs carry `facts: []` — facts are reserved for the 13
// hand-built architecture specs. Anything outside the subset fails loudly
// with the offending line.

import { existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const APP_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const REPO_ROOT = path.resolve(APP_ROOT, "../..");
const AUTO_DIR = path.join(APP_ROOT, "src", "diagrams", "auto");

// Mirror of libs/portfolio-core/src/portfolio_core/story.py SECTION_TITLES so
// generated diagram titles match the section headings they sit under.
const SECTION_TITLES = {
  background: "Background",
  objectives: "Target & objectives",
  data: "Data",
  eda: "Exploratory analysis",
  training: "Training & methods",
  evaluation: "Evaluation setup",
  results: "Results",
  conclusions: "Conclusions & lessons",
};

// Hand-review overrides from the Wave D visual pass (playwright screenshots of
// the converted corpus). Keyed by spec id; `labels` maps flat node ids to
// replacement labels, `canvasHeight` pins the auto-sized canvas cap.
const SPEC_OVERRIDES = {
  // Self-loop graph: the auto-height fit under-computes dagre's rank margins
  // and the bottom rank (Critique / WorkflowResult) clipped.
  "auto-09-agentic-workflows-4": { canvasHeight: 480 },
  // Subgraph-annotated gate label wrapped into unreadable "·" shards.
  "auto-01-rag-agent-4": { labels: { "verify-sp": "Verify loop: 0.6 support floor vs cited chunk?" } },
};

const ARTICLE_SOURCES = [  {
    specId: "auto-app-agent-chat-1",
    title: "Chatbot agent — human approval for consequential tools",
    file: "src/pages/AgentChatArticle.tsx",
    constName: "APPROVAL_FLOW",
  },
  {
    specId: "auto-app-document-intelligence-1",
    title: "Document intelligence — page-scoped cited chat",
    file: "src/pages/DocumentIntelligenceArticle.tsx",
    constName: "CHAT_FLOW",
  },
];

const flattenLabel = (raw) =>
  raw
    .replace(/<br\s*\/?>/gi, " · ")
    .replace(/\s+/g, " ")
    .trim();

const slug = (raw) => {
  const s = raw
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return s || "node";
};

// ---------------------------------------------------------------------------
// Parsing
// ---------------------------------------------------------------------------

function parseMermaid(block, where) {
  const nodes = new Map(); // raw id → { id, label, shape, kind, subgraph }
  const subgraphs = new Map(); // raw id → { id, label, members, internalEdges }
  const edges = []; // { source(raw), target(raw), kind, label }
  const errors = [];
  let direction = "LR";
  let headerSeen = false;
  let currentSubgraph = null;

  const fail = (line, why) => errors.push(`${where}: ${why}: ${line.trim()}`);

  const cleanEdgeLabel = (raw) => {
    const unquoted = raw.trim().replace(/^"(.*)"$/, "$1");
    return flattenLabel(unquoted) || undefined;
  };

  // Edge operator at the start of `text`, with its optional label.
  const matchOperator = (text) => {
    let m;
    if ((m = /^-\.->\s*\|([^|]*)\|/.exec(text))) {
      return { kind: "result", label: cleanEdgeLabel(m[1]), consumed: m[0].length };
    }
    if ((m = /^-\.->/.exec(text))) return { kind: "result", label: undefined, consumed: m[0].length };
    if ((m = /^-->\s*\|([^|]*)\|/.exec(text))) {
      return { kind: "task", label: cleanEdgeLabel(m[1]), consumed: m[0].length };
    }
    if ((m = /^-->/.exec(text))) return { kind: "task", label: undefined, consumed: m[0].length };
    if ((m = /^---/.exec(text))) return { kind: "result", label: undefined, consumed: m[0].length };
    if ((m = /^--\s+(.+?)\s+-->/.exec(text))) {
      return { kind: "task", label: cleanEdgeLabel(m[1]), consumed: m[0].length };
    }
    return null;
  };

  const SHAPES = [
    { open: '["', close: '"]', shape: "rect" },
    { open: '{"', close: '"}', shape: "rhombus" },
    { open: '[("', close: ')]', shape: "cylinder" },
    { open: "[[", close: "]]", shape: "subroutine" },
    { open: '("', close: '")', shape: "stadium" },
  ];

  // Node ref at the start of `text`: id plus an optional quoted shaped label.
  const parseNodeRef = (text) => {
    const bare = /^([A-Za-z0-9_]+)/.exec(text);
    if (!bare) return null;
    const id = bare[0];
    let consumed = id.length;
    let shape = null;
    let label;
    for (const s of SHAPES) {
      if (!text.startsWith(s.open, consumed)) continue;
      const closeIdx = text.indexOf(s.close, consumed + s.open.length);
      if (closeIdx === -1) {
        fail(text, `unterminated ${s.shape} label`);
        return null;
      }
      label = flattenLabel(text.slice(consumed + s.open.length, closeIdx));
      shape = s.shape;
      consumed = closeIdx + s.close.length;
      break;
    }
    return { id, shape, label, consumed };
  };

  const addNode = (rawId, shape, label, subgraphId) => {
    if (!rawId) return;
    if (subgraphs.has(rawId)) {
      // A bare reference to a subgraph id is an edge endpoint, resolved by
      // the flattener; only a shaped/labeled declaration collides for real.
      if (shape || label) fail(rawId, "node id collides with a subgraph id");
      return;
    }
    if (nodes.has(rawId)) {
      const existing = nodes.get(rawId);
      if (label) existing.label = label;
      if (shape) existing.shape = shape;
      return;
    }
    nodes.set(rawId, {
      id: rawId,
      label: label ?? rawId,
      shape: shape ?? "rect",
      // Stadium nodes resolve to source/output once edges are known.
      kind:
        shape === "rhombus"
          ? "gate"
          : shape === "cylinder"
            ? "data"
            : shape === "subroutine"
              ? "agent"
              : shape === "stadium"
                ? "stadium"
                : "tool",
      subgraph: subgraphId ?? null,
    });
  };

  // Statement tokenizer: alternates node refs and edge operators, so both
  // `A["x"] --> B --> C{"y"}` and `ID --- Q["q"] --- TOOLS["t"]` parse.
  const parseStatement = (line) => {
    let rest = line.trim();
    let pendingNode = null;
    while (rest !== "") {
      if (pendingNode !== null) {
        const op = matchOperator(rest);
        if (op) {
          rest = rest.slice(op.consumed).trimStart();
          const nodeMatch = parseNodeRef(rest);
          if (!nodeMatch) {
            fail(line, `edge "${op.kind}" is not followed by a node`);
            return;
          }
          rest = rest.slice(nodeMatch.consumed).trimStart();
          addNode(nodeMatch.id, nodeMatch.shape, nodeMatch.label, currentSubgraph?.id ?? null);
          edges.push({ source: pendingNode, target: nodeMatch.id, kind: op.kind, label: op.label });
          pendingNode = nodeMatch.id;
          continue;
        }
      }
      const nodeMatch = parseNodeRef(rest);
      if (nodeMatch && pendingNode === null) {
        rest = rest.slice(nodeMatch.consumed).trimStart();
        addNode(nodeMatch.id, nodeMatch.shape, nodeMatch.label, currentSubgraph?.id ?? null);
        pendingNode = nodeMatch.id;
        continue;
      }
      fail(line, `unparsed statement tail "${rest}"`);
      return;
    }
  };

  for (const rawLine of block) {
    const line = rawLine.trim();
    if (line === "") continue;
    if (!headerSeen) {
      const header = /^(?:graph|flowchart)\s+(LR|TB|TD|BT|RL)\b/.exec(line);
      if (!header) {
        fail(rawLine, "expected a `graph|flowchart <direction>` header");
        continue;
      }
      direction = header[1] === "TD" ? "TB" : header[1];
      headerSeen = true;
      continue;
    }
    if (/^end\b/.test(line)) {
      if (!currentSubgraph) fail(rawLine, "`end` without a subgraph");
      else currentSubgraph = null;
      continue;
    }
    const sub = /^subgraph\s+([A-Za-z0-9_]+)(?:\["([^"]*)"\])?/.exec(line);
    if (sub) {
      if (currentSubgraph) {
        fail(rawLine, "nested subgraphs are not supported");
        continue;
      }
      if (nodes.has(sub[1])) fail(sub[1], "subgraph id collides with a node id");
      currentSubgraph = {
        id: sub[1],
        label: flattenLabel(sub[2] ?? sub[1]),
        members: [],
        internalEdges: [],
      };
      subgraphs.set(sub[1], currentSubgraph);
      continue;
    }
    if (/^direction\s+(LR|TB|TD|BT|RL)\b/.test(line)) continue; // layout hint only
    parseStatement(line);
  }

  if (!headerSeen) errors.push(`${where}: missing graph/flowchart header`);

  for (const node of nodes.values()) {
    if (node.subgraph && subgraphs.has(node.subgraph)) {
      subgraphs.get(node.subgraph).members.push(node.id);
    }
  }
  for (const edge of edges) {
    for (const sub of subgraphs.values()) {
      if (sub.members.includes(edge.source) && sub.members.includes(edge.target)) {
        sub.internalEdges.push(edge);
      }
    }
  }

  // Stadium nodes: terminal (no outgoing edges) → output, otherwise source.
  const outgoing = new Set(edges.map((e) => e.source));
  for (const node of nodes.values()) {
    if (node.shape === "stadium") node.kind = outgoing.has(node.id) ? "source" : "output";
  }

  return { nodes, subgraphs, edges, direction, errors };
}

// ---------------------------------------------------------------------------
// Subgraph flattening
// ---------------------------------------------------------------------------

/** Entry members have no incoming internal edge; exits have no outgoing one.
 *  A subgraph without internal edges uses all members on both sides — that is
 *  what a mermaid box-to-box edge means: the whole record flows across. */
function flatten(parsed) {
  const { nodes, subgraphs, edges } = parsed;
  const flat = new Map(); // raw id → flat node
  for (const [rawId, node] of nodes) {
    const flatId = node.subgraph ? `${slug(node.subgraph)}-${slug(rawId)}` : slug(rawId);
    flat.set(rawId, { ...node, id: flatId });
  }
  const ids = new Set();
  for (const node of flat.values()) {
    if (ids.has(node.id)) throw new Error(`duplicate flat node id: ${node.id}`);
    ids.add(node.id);
  }

  // Note the subgraph name on the first member's label.
  for (const sub of subgraphs.values()) {
    if (sub.members.length === 0) continue;
    const first = flat.get(sub.members[0]);
    first.label = `${sub.label} · ${first.label}`;
  }

  const memberIds = (sub) => sub.members.map((m) => flat.get(m).id);
  const endpoints = (rawId, side) => {
    const sub = subgraphs.get(rawId);
    if (!sub) return [flat.get(rawId).id];
    if (sub.internalEdges.length === 0) return memberIds(sub);
    const internal = sub.internalEdges;
    const blocked = new Set(internal.map((e) => (side === "entry" ? e.target : e.source)));
    return sub.members.filter((m) => !blocked.has(m)).map((m) => flat.get(m).id);
  };

  const flatEdges = [];
  const seenEdgeIds = new Set();
  for (const edge of edges) {
    // A label belongs to the mermaid edge, not to every expanded pair — when a
    // subgraph edge expands to several flat edges, label only the first.
    let first = true;
    for (const source of endpoints(edge.source, "exit")) {
      for (const target of endpoints(edge.target, "entry")) {
        let id = `${source}-${target}`;
        let n = 2;
        while (seenEdgeIds.has(id)) id = `${source}-${target}-${n++}`;
        seenEdgeIds.add(id);
        flatEdges.push({ id, source, target, kind: edge.kind, label: first ? edge.label : undefined });
        first = false;
      }
    }
  }

  return {
    nodes: [...flat.values()].map((n) => ({ id: n.id, label: n.label, kind: n.kind })),
    edges: flatEdges,
  };
}

// ---------------------------------------------------------------------------
// Emission
// ---------------------------------------------------------------------------

function emitSpec(specId, title, parsed, origin) {
  const overrides = SPEC_OVERRIDES[specId] ?? {};
  const labelOverrides = overrides.labels ?? {};
  const { nodes, edges } = flatten(parsed);
  const finalNodes = nodes.map((n) =>
    labelOverrides[n.id] ? { ...n, label: labelOverrides[n.id] } : n,
  );
  const canvasHeight = overrides.canvasHeight
    ? `  canvasHeight: ${overrides.canvasHeight},\n`
    : "";
  const constName =
    "AUTO_" +
    specId
      .replace(/^auto-/, "")
      .replace(/[^a-zA-Z0-9]+/g, "_")
      .toUpperCase()
      .replace(/_+/g, "_") +
    "_SPEC";
  const nodeLines = finalNodes
    .map(
      (n) =>
        `    {\n      id: ${JSON.stringify(n.id)},\n      label: ${JSON.stringify(n.label)},\n      kind: ${JSON.stringify(n.kind)},\n      facts: [],\n    },`,
    )
    .join("\n");
  const edgeLines = edges
    .map((e) => {
      const label = e.label ? `, label: ${JSON.stringify(e.label)}` : "";
      return `    { id: ${JSON.stringify(e.id)}, source: ${JSON.stringify(e.source)}, target: ${JSON.stringify(e.target)}, kind: ${JSON.stringify(e.kind)}${label} },`;
    })
    .join("\n");
  return {
    fileName: `${specId.replace(/^auto-/, "")}.ts`,
    constName,
    content: `import type { DiagramSpec } from "../types";

// Generated by scripts/mermaid-to-flow.mjs from ${origin} — do not hand-edit;
// re-run the converter. facts stay empty: reserved for the hand-built
// architecture specs.
export const ${constName} = {
  id: ${JSON.stringify(specId)},
  title: ${JSON.stringify(title)},
  direction: ${JSON.stringify(parsed.direction)},
${canvasHeight}  nodes: [
${nodeLines}
  ],
  edges: [
${edgeLines}
  ],
} as const satisfies DiagramSpec;
`,
  };
}

// ---------------------------------------------------------------------------
// Sources
// ---------------------------------------------------------------------------

function projectTitle(projectDir) {
  const manifest = path.join(REPO_ROOT, "projects", projectDir, "portfolio.yaml");
  const match = /^title:\s*(.+)$/m.exec(readFileSync(manifest, "utf8"));
  return match ? match[1].trim() : projectDir;
}

function sectionTitle(sectionId) {
  return (
    SECTION_TITLES[sectionId] ??
    sectionId.replace(/[_-]+/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
  );
}

/** Scan one story.yaml for mermaid fences and their enclosing section. */
function scanStory(filePath, projectDir) {
  const lines = readFileSync(filePath, "utf8").split("\n");
  const blocks = [];
  let sectionId = null;
  const title = projectTitle(projectDir);
  for (let i = 0; i < lines.length; i++) {
    const section = /^(\s*)- id:\s*([A-Za-z0-9_-]+)\s*$/.exec(lines[i]);
    if (section && section[1].length <= 2) sectionId = section[2];
    const fence = /^(\s*)```mermaid\s*$/.exec(lines[i]);
    if (!fence) continue;
    const indent = fence[1];
    const block = [];
    let j = i + 1;
    while (j < lines.length && lines[j] !== `${indent}\`\`\`` && !/^\s*```\s*$/.test(lines[j])) {
      block.push(lines[j]);
      j++;
    }
    if (j >= lines.length) throw new Error(`${filePath}:${i + 1}: unterminated mermaid fence`);
    const n = blocks.length + 1;
    blocks.push({
      specId: `auto-${projectDir}-${n}`,
      title: `${title} — ${sectionTitle(sectionId)}`,
      block,
      indent,
      startLine: i,
      endLine: j,
    });
    i = j;
  }
  return { lines, blocks };
}

function scanArticle(article) {
  const filePath = path.join(APP_ROOT, article.file);
  const source = readFileSync(filePath, "utf8");
  // The article sources hold the fence inside a template literal: the file
  // bytes are a raw opening backtick, then \`-escaped inner backticks.
  const marker = `const ${article.constName} = \`\\\`\\\`\\\`mermaid\n`;
  const start = source.indexOf(marker);
  if (start === -1) return null;
  const bodyStart = start + marker.length;
  const end = source.indexOf("\n\\`\\`\\`", bodyStart);
  if (end === -1) throw new Error(`${article.file}: unterminated ${article.constName} literal`);
  return { ...article, block: source.slice(bodyStart, end).split("\n") };
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

let generated = 0;
const warnings = [];
const allErrors = [];

function convertBlock(specId, title, block, origin) {
  const parsed = parseMermaid(block, origin);
  if (parsed.errors.length > 0) {
    allErrors.push(...parsed.errors);
    return false;
  }
  const emitted = emitSpec(specId, title, parsed, origin);
  writeFileSync(path.join(AUTO_DIR, emitted.fileName), emitted.content);
  generated++;
  return true;
}

// The barrel registry reflects every spec file committed in src/diagrams/auto
// (not just the blocks converted in this run), so re-runs stay idempotent.
function writeBarrel() {
  const specs = readdirSync(AUTO_DIR)
    .filter((f) => f.endsWith(".ts") && f !== "index.ts")
    .map((fileName) => {
      const content = readFileSync(path.join(AUTO_DIR, fileName), "utf8");
      const specId = /id: "(auto-[^"]+)"/.exec(content)?.[1];
      const constName = /export const (\w+) = \{/.exec(content)?.[1];
      if (!specId || !constName) throw new Error(`src/diagrams/auto/${fileName}: missing id/export const`);
      return { specId, constName, fileName };
    })
    .sort((a, b) => a.specId.localeCompare(b.specId));
  const imports = specs
    .map((r) => `import { ${r.constName} } from "./${r.fileName.replace(/\.ts$/, "")}";`)
    .join("\n");
  const entries = specs.map((r) => `  ${JSON.stringify(r.specId)}: ${r.constName},`).join("\n");
  writeFileSync(
    path.join(AUTO_DIR, "index.ts"),
    `import type { DiagramSpec } from "../types";\n\n${imports}\n\nexport const AUTO_DIAGRAM_SPECS = {\n${entries}\n} as const satisfies Record<string, DiagramSpec>;\n`,
  );
  return specs.length;
}

function main() {
  mkdirSync(AUTO_DIR, { recursive: true });
  const storyDirs = readdirSync(path.join(REPO_ROOT, "projects"))
    .filter((d) => /^\d{2}-/.test(d) && existsSync(path.join(REPO_ROOT, "projects", d, "story.yaml")))
    .sort();

  for (const dir of storyDirs) {
    const filePath = path.join(REPO_ROOT, "projects", dir, "story.yaml");
    const { lines, blocks } = scanStory(filePath, dir);
    const replaced = [...lines];
    let delta = 0;
    for (const b of blocks) {
      if (!convertBlock(b.specId, b.title, b.block, `${dir}/story.yaml`)) continue;
      replaced.splice(
        b.startLine + delta,
        b.endLine - b.startLine + 1,
        `${b.indent}\`\`\`diagram ${b.specId}`,
        `${b.indent}\`\`\``,
      );
      delta += 2 - (b.endLine - b.startLine + 1);
    }
    if (blocks.length > 0) writeFileSync(filePath, replaced.join("\n"));
    console.log(`${dir}: ${blocks.length} block(s) converted`);
  }

  for (const article of ARTICLE_SOURCES) {
    const found = scanArticle(article);
    if (!found) {
      warnings.push(
        `${article.file}: no ${article.constName} mermaid literal (already migrated?) — spec not regenerated`,
      );
      continue;
    }
    convertBlock(found.specId, found.title, found.block, article.file);
    console.log(`${article.file}: 1 block converted (${found.specId})`);
  }

  for (const w of warnings) console.warn(`warning: ${w}`);
  if (allErrors.length > 0) {
    for (const e of allErrors) console.error(`error: ${e}`);
    process.exitCode = 1;
    return;
  }
  const registered = writeBarrel();
  console.log(`generated ${generated} spec(s) this run; ${registered} registered in src/diagrams/auto/index.ts`);
}

main();
