import type { ReactNode } from "react";

// Minimal, safe markdown → React renderer. Supports only what story.yaml
// prose uses: paragraphs, **bold**, *emphasis*, `code`, -/* / 1. lists, and
// pipe tables (header + `|---|` separator line). Everything is rendered as
// React text nodes — no HTML injection surface.

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
const OL_ITEM_RE = /^\s*\d+\.\s+/;
// GFM separator row: only pipes, dashes, colons and whitespace; needs a dash.
const TABLE_SEP_RE = /^\s*\|?[\s:|-]+\|?\s*$/;

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
    <table key={keyPrefix}>
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
  );
}

export function renderMarkdown(md: string): ReactNode[] {
  const blocks = md.split(/\n{2,}/);
  const out: ReactNode[] = [];
  blocks.forEach((block, bi) => {
    const lines = block.split("\n").filter((l) => l.trim() !== "");
    if (lines.length === 0) return;
    // Table: a separator line with a pipe-containing header directly above it.
    const sepIdx = lines.findIndex((l, i) => i >= 1 && isTableSeparator(l));
    if (sepIdx > 0 && lines[sepIdx - 1].includes("|")) {
      const rowLines = lines.slice(sepIdx + 1).filter((l) => l.includes("|"));
      out.push(renderTable(lines[sepIdx - 1], rowLines, `b${bi}`));
    } else if (lines.every((l) => UL_ITEM_RE.test(l))) {
      out.push(
        <ul key={`b${bi}`}>
          {lines.map((l, li) => (
            <li key={`b${bi}i${li}`}>{renderInline(l.replace(UL_ITEM_RE, ""), `b${bi}i${li}`)}</li>
          ))}
        </ul>,
      );
    } else if (lines.every((l) => OL_ITEM_RE.test(l))) {
      out.push(
        <ol key={`b${bi}`}>
          {lines.map((l, li) => (
            <li key={`b${bi}i${li}`}>{renderInline(l.replace(OL_ITEM_RE, ""), `b${bi}i${li}`)}</li>
          ))}
        </ol>,
      );
    } else {
      out.push(<p key={`b${bi}`}>{renderInline(lines.join(" "), `b${bi}`)}</p>);
    }
  });
  return out;
}
