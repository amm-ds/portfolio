import type { ReactNode } from "react";
import { MermaidDiagram } from "../components/MermaidDiagram";

// Minimal, safe markdown → React renderer. Supports what story.yaml prose
// uses: paragraphs, **bold**, *emphasis*, `code`, -/* / N. / N) lists, pipe
// tables, and fenced code blocks (```lang; ```mermaid renders as a diagram).
// Everything is rendered as React text nodes — no HTML injection surface.

const INLINE_RE = /(`[^`\n]+`|\*\*[^*]+\*\*|\*[^*\n]+\*)/g;

function renderInline(text: string, keyPrefix: string): ReactNode[] {
  const parts = text.split(INLINE_RE);
  return parts.map((part, i) => {
    const key = `${keyPrefix}-${i}`;
    if (part.startsWith("`") && part.endsWith("`") && part.length > 1) {
      return <code key={key}>{part.slice(1, -1)}</code>;
    }
    if (part.startsWith("**") && part.endsWith("**") && part.length > 3) {
      return <strong key={key}>{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith("*") && part.endsWith("*") && part.length > 1) {
      return <em key={key}>{part.slice(1, -1)}</em>;
    }
    return part;
  });
}

const UL_ITEM_RE = /^\s*[-*]\s+/;
const OL_ITEM_RE = /^\s*\d+[.)]\s+/;
// GFM separator row: only pipes, dashes, colons and whitespace; needs a dash.
const TABLE_SEP_RE = /^\s*\|?[\s:|-]+\|?\s*$/;
const FENCE_RE = /^\s*```/;

function isTableSeparator(line: string): boolean {
  return line.includes("-") && TABLE_SEP_RE.test(line);
}

/** Split a pipe row into trimmed cells, dropping outer-pipe empty cells. */
export function splitTableCells(line: string): string[] {
  const raw = line
    .trim()
    .split("|")
    .map((c) => c.trim());
  const cells = raw[0] === "" ? raw.slice(1) : raw;
  return cells.length > 0 && cells[cells.length - 1] === "" ? cells.slice(0, -1) : cells;
}

function renderTable(
  headerLine: string,
  rowLines: string[],
  keyPrefix: string,
): ReactNode {
  const header = splitTableCells(headerLine);
  const rows = rowLines.map(splitTableCells);
  return (
    <div className="table-scroll" key={keyPrefix}>
      <table className="data-table">
        <thead>
          <tr>
            {header.map((c, ci) => (
              <th key={ci}>{renderInline(c, `${keyPrefix}h${ci}`)}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, ri) => (
            <tr key={ri}>
              {r.map((c, ci) => (
                <td key={ci}>{renderInline(c, `${keyPrefix}r${ri}c${ci}`)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Render one blank-line-separated block of lines (no fences). */
function renderBlock(lines: string[], keyPrefix: string): ReactNode {
  const sepIdx = lines.findIndex((l, i) => i >= 1 && isTableSeparator(l));
  if (sepIdx > 0 && lines[sepIdx - 1].includes("|")) {
    const rowLines = lines.slice(sepIdx + 1).filter((l) => l.includes("|"));
    return renderTable(lines[sepIdx - 1], rowLines, keyPrefix);
  }
  if (lines.every((l) => UL_ITEM_RE.test(l))) {
    return (
      <ul key={keyPrefix}>
        {lines.map((l, li) => (
          <li key={li}>{renderInline(l.replace(UL_ITEM_RE, ""), `${keyPrefix}i${li}`)}</li>
        ))}
      </ul>
    );
  }
  if (lines.every((l) => OL_ITEM_RE.test(l))) {
    return (
      <ol key={keyPrefix}>
        {lines.map((l, li) => (
          <li key={li}>{renderInline(l.replace(OL_ITEM_RE, ""), `${keyPrefix}i${li}`)}</li>
        ))}
      </ol>
    );
  }
  return <p key={keyPrefix}>{renderInline(lines.join(" "), keyPrefix)}</p>;
}

function renderCodeBlock(code: string, lang: string, keyPrefix: string): ReactNode {
  if (lang === "mermaid") {
    return <MermaidDiagram key={keyPrefix} code={code} />;
  }
  return (
    <pre key={keyPrefix} className="code-block">
      <code>{code}</code>
    </pre>
  );
}

export function renderMarkdown(md: string): ReactNode[] {
  const out: ReactNode[] = [];
  const lines = md.split("\n");
  let block: string[] = [];
  let key = 0;

  const flushBlock = () => {
    if (block.length > 0) {
      out.push(renderBlock(block, `b${key++}`));
      block = [];
    }
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (FENCE_RE.test(line)) {
      // Fenced code is atomic: swallow blank lines inside the fence.
      flushBlock();
      const lang = line.trim().replace(/^```/, "").trim();
      const codeLines: string[] = [];
      i++;
      while (i < lines.length && !/^\s*```\s*$/.test(lines[i])) {
        codeLines.push(lines[i]);
        i++;
      }
      out.push(renderCodeBlock(codeLines.join("\n"), lang, `b${key++}`));
    } else if (line.trim() === "") {
      flushBlock();
    } else {
      block.push(line);
    }
  }
  flushBlock();
  return out;
}
