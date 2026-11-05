/**
 * Tiny markdown renderer for chat text: paragraphs, fenced code blocks,
 * unordered lists, inline code / bold / italic / links. Emits React nodes
 * only (no raw HTML), so untrusted model output cannot inject markup.
 */
import type { ReactNode } from "react";

const INLINE_RE = /(`[^`\n]+`)|(\*\*[^*\n]+\*\*)|(\*[^*\n]+\*)|(\[[^\]\n]+\]\([^)\n]+\))/;

function inline(text: string, keyBase: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  let rest = text;
  let i = 0;
  while (rest !== "") {
    const match = INLINE_RE.exec(rest);
    if (!match) {
      nodes.push(rest);
      break;
    }
    const [token, code, bold, italic, link] = match;
    if (match.index > 0) nodes.push(rest.slice(0, match.index));
    const key = `${keyBase}-${i++}`;
    if (code) {
      nodes.push(<code key={key}>{code.slice(1, -1)}</code>);
    } else if (bold) {
      nodes.push(<strong key={key}>{inline(bold.slice(2, -2), key)}</strong>);
    } else if (italic) {
      nodes.push(<em key={key}>{inline(italic.slice(1, -1), key)}</em>);
    } else if (link) {
      const closing = link.indexOf("](");
      const label = link.slice(1, closing);
      const href = link.slice(closing + 2, -1);
      nodes.push(
        <a key={key} href={href} target="_blank" rel="noreferrer">
          {label}
        </a>,
      );
    }
    rest = rest.slice(match.index + token.length);
  }
  return nodes;
}

export function Markdown({ text }: { text: string }) {
  const blocks: ReactNode[] = [];
  const lines = text.split("\n");
  let paragraph: string[] = [];
  let list: string[] = [];
  let code: string[] | null = null;
  let key = 0;

  const flushParagraph = () => {
    if (paragraph.length > 0) {
      blocks.push(
        <p key={key++} className="md-p">
          {inline(paragraph.join(" "), `p${key}`)}
        </p>,
      );
      paragraph = [];
    }
  };
  const flushList = () => {
    if (list.length > 0) {
      blocks.push(
        <ul key={key++} className="md-ul">
          {list.map((item, i) => (
            <li key={i}>{inline(item, `li${key}-${i}`)}</li>
          ))}
        </ul>,
      );
      list = [];
    }
  };

  for (const line of lines) {
    if (code !== null) {
      if (line.startsWith("```")) {
        blocks.push(
          <pre key={key++} className="md-pre">
            <code>{code.join("\n")}</code>
          </pre>,
        );
        code = null;
      } else {
        code.push(line);
      }
      continue;
    }
    if (line.startsWith("```")) {
      flushParagraph();
      flushList();
      code = [];
    } else if (/^\s*[-*] /.test(line)) {
      flushParagraph();
      list.push(line.replace(/^\s*[-*] /, ""));
    } else if (line.trim() === "") {
      flushParagraph();
      flushList();
    } else {
      flushList();
      paragraph.push(line);
    }
  }
  // Unclosed fence: render what accumulated as plain text.
  if (code !== null && code.length > 0) {
    blocks.push(
      <pre key={key++} className="md-pre">
        <code>{code.join("\n")}</code>
      </pre>,
    );
  }
  flushParagraph();
  flushList();

  return <div className="md">{blocks}</div>;
}
