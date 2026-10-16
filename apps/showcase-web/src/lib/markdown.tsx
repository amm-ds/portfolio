import { Fragment, type ReactNode } from "react";
import { MermaidDiagram } from "../components/MermaidDiagram";

// Minimal, safe markdown → React renderer. Supports what story.yaml prose
// uses: paragraphs, **bold**, *emphasis*, `code`, -/* / N. / N) lists (with
// GFM-style indented continuation lines for wrapped items), pipe tables,
// thematic breaks (---/***/___), and fenced code blocks (```lang; ```mermaid
// renders as a diagram). Everything is rendered as React text nodes — no HTML
// injection surface.

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
// Thematic break: --- / *** / ___ (surrounding whitespace allowed).
const HR_RE = /^\s*(?:-{3}|\*{3}|_{3})\s*$/;
// Indented (2+ spaces) non-item line: continuation of the preceding list item.
const CONTINUATION_RE = /^\s{2,}\S/;

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
  // A list starts when the block's FIRST line is an item. Later lines either
  // match the item pattern (new item), are indented 2+ spaces (continuation
  // of the previous item, joined with a space), or end the list and begin a
  // new paragraph block.
  const ordered = lines.length > 0 && OL_ITEM_RE.test(lines[0]);
  const unordered = !ordered && lines.length > 0 && UL_ITEM_RE.test(lines[0]);
  if (ordered || unordered) {
    const itemRe = unordered ? UL_ITEM_RE : OL_ITEM_RE;
    const items: string[] = [];
    let rest: string[] | null = null;
    for (const l of lines) {
      if (rest) {
        rest.push(l);
      } else if (itemRe.test(l)) {
        items.push(l.replace(itemRe, "").trim());
      } else if (items.length > 0 && CONTINUATION_RE.test(l)) {
        items[items.length - 1] += ` ${l.trim()}`;
      } else {
        rest = [l];
      }
    }
    const list = ordered ? (
      <ol key={keyPrefix}>
        {items.map((text, li) => (
          <li key={li}>{renderInline(text, `${keyPrefix}i${li}`)}</li>
        ))}
      </ol>
    ) : (
      <ul key={keyPrefix}>
        {items.map((text, li) => (
          <li key={li}>{renderInline(text, `${keyPrefix}i${li}`)}</li>
        ))}
      </ul>
    );
    if (rest) {
      return (
        <Fragment key={keyPrefix}>
          {list}
          {renderBlock(rest, `${keyPrefix}x`)}
        </Fragment>
      );
    }
    return list;
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
    } else if (HR_RE.test(line)) {
      flushBlock();
      out.push(<hr key={`b${key++}`} className="md-break" />);
    } else if (line.trim() === "") {
      flushBlock();
    } else {
      block.push(line);
    }
  }
  flushBlock();
  return out;
}
