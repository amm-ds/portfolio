import type { ReactNode } from "react";

// Minimal, safe markdown → React renderer. Supports only what story.yaml
// prose uses: paragraphs, **bold**, *emphasis*, `code`, and -/* / 1. lists.
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
const OL_ITEM_RE = /^\s*\d+\.\s+/;

export function renderMarkdown(md: string): ReactNode[] {
  const blocks = md.split(/\n{2,}/);
  const out: ReactNode[] = [];
  blocks.forEach((block, bi) => {
    const lines = block.split("\n").filter((l) => l.trim() !== "");
    if (lines.length === 0) return;
    if (lines.every((l) => UL_ITEM_RE.test(l))) {
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
