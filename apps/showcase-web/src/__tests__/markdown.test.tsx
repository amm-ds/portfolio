import { readFileSync } from "node:fs";
import { render, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { renderMarkdown } from "../lib/markdown";

vi.mock("mermaid", () => ({
  default: {
    initialize: vi.fn(),
    render: vi.fn(async () => ({ svg: '<svg data-mock="mermaid-svg"></svg>' })),
  },
}));

function renderToText(md: string): string {
  const { container } = render(<>{renderMarkdown(md)}</>);
  return container.textContent ?? "";
}

describe("renderMarkdown", () => {
  it("renders plain paragraphs", () => {
    const { container } = render(<>{renderMarkdown("hello world")}</>);
    expect(container.querySelector("p")?.textContent).toBe("hello world");
  });

  it("renders separate paragraphs for blank-line-separated blocks", () => {
    const { container } = render(<>{renderMarkdown("one\n\ntwo")}</>);
    const ps = container.querySelectorAll("p");
    expect(ps).toHaveLength(2);
    expect(ps[0].textContent).toBe("one");
    expect(ps[1].textContent).toBe("two");
  });

  it("renders **bold** as <strong>", () => {
    const { container } = render(<>{renderMarkdown("a **bold move** here")}</>);
    const strong = container.querySelector("strong");
    expect(strong?.textContent).toBe("bold move");
    expect(renderToText("a **bold move** here")).toBe("a bold move here");
  });

  it("renders *emphasis* as <em>", () => {
    const { container } = render(<>{renderMarkdown("an *italic* word")}</>);
    expect(container.querySelector("em")?.textContent).toBe("italic");
  });

  it("renders `code` as <code> without backticks", () => {
    const { container } = render(<>{renderMarkdown("run `dvc repro` now")}</>);
    const code = container.querySelector("code");
    expect(code?.textContent).toBe("dvc repro");
  });

  it("renders unordered lists", () => {
    const { container } = render(<>{renderMarkdown("- first\n- second\n- third")}</>);
    const items = container.querySelectorAll("ul li");
    expect(items).toHaveLength(3);
    expect(items[1].textContent).toBe("second");
  });

  it("renders ordered lists", () => {
    const { container } = render(<>{renderMarkdown("1. step one\n2. step two")}</>);
    const items = container.querySelectorAll("ol li");
    expect(items).toHaveLength(2);
    expect(items[0].textContent).toBe("step one");
  });

  it("renders inline formatting inside list items", () => {
    const { container } = render(<>{renderMarkdown("- a **key** point")}</>);
    expect(container.querySelector("li strong")?.textContent).toBe("key");
  });

  it("emits no raw HTML for script injection attempts", () => {
    const { container } = render(
      <>{renderMarkdown('<script>alert(1)</script> and <img src=x onerror=alert(1)>')}</>,
    );
    expect(container.querySelector("script")).toBeNull();
    expect(container.querySelector("img")).toBeNull();
    expect(container.textContent).toContain("<script>alert(1)</script>");
  });

  it("renders [text](url) as an external anchor for allowed schemes", () => {
    const { container } = render(
      <>{renderMarkdown("see the [M5 dataset](https://www.kaggle.com/c/m5-forecasting-accuracy)")}</>,
    );
    const a = container.querySelector("a");
    expect(a?.textContent).toBe("M5 dataset");
    expect(a?.getAttribute("href")).toBe("https://www.kaggle.com/c/m5-forecasting-accuracy");
    expect(a?.getAttribute("target")).toBe("_blank");
    expect(a?.getAttribute("rel")).toContain("noopener");
  });

  it("renders mailto links and keeps link text inside lists and tables", () => {
    const { container } = render(
      <>{renderMarkdown("- mail [me](mailto:hi@example.com)\n\n| a |\n|---|\n| [x](https://example.com) |")}</>,
    );
    const links = container.querySelectorAll("a");
    expect(links).toHaveLength(2);
    expect(links[0].getAttribute("href")).toBe("mailto:hi@example.com");
    expect(container.querySelector("td a")?.textContent).toBe("x");
  });

  it("leaves disallowed schemes and relative paths as literal text", () => {
    const { container } = render(
      <>{renderMarkdown("a [click](javascript:alert(1)) and a [relative](/glossary)")}</>,
    );
    expect(container.querySelector("a")).toBeNull();
    expect(container.textContent).toContain("a [click](javascript:alert(1))");
    expect(container.textContent).toContain("and a [relative](/glossary)");
  });

  it("does not glossary-link terms inside link text", () => {
    const { container } = render(
      <>{renderMarkdown("the [baseline docs](https://example.com/baseline) page")}</>,
    );
    const a = container.querySelector("a");
    expect(a?.textContent).toBe("baseline docs");
    expect(a?.querySelector(".glossary-term")).toBeNull();
    expect(container.querySelectorAll("a")).toHaveLength(1);
  });

  it("renders ATX headings below the section h2 without ever emitting h1/h2", () => {
    const { container } = render(
      <>{renderMarkdown("## Exact numbers\n\nbody\n\n### Deeper\n\nmore")}</>,
    );
    const h3 = container.querySelector("h3.md-heading");
    const h4 = container.querySelector("h4.md-heading");
    expect(h3?.textContent).toBe("Exact numbers");
    expect(h4?.textContent).toBe("Deeper");
    expect(container.querySelector("h1, h2")).toBeNull();
  });
});

describe("renderMarkdown tables", () => {
  const TABLE_MD = "| model | mae |\n|---|---|\n| naive_last | 100 |\n| tuned | 72 |";

  it("renders a pipe table with thead/th and tbody/td", () => {
    const { container } = render(<>{renderMarkdown(TABLE_MD)}</>);
    const table = container.querySelector("table")!;
    expect(table).not.toBeNull();
    const ths = [...table.querySelectorAll("thead th")].map((el) => el.textContent);
    expect(ths).toEqual(["model", "mae"]);
    const rows = table.querySelectorAll("tbody tr");
    expect(rows).toHaveLength(2);
    expect(rows[1].querySelectorAll("td")[0].textContent).toBe("tuned");
    expect(rows[1].querySelectorAll("td")[1].textContent).toBe("72");
  });

  it("accepts alignment colons in the separator row", () => {
    const md = "| a | b |\n|:---|---:|\n| 1 | 2 |";
    const { container } = render(<>{renderMarkdown(md)}</>);
    expect(container.querySelectorAll("tbody tr")).toHaveLength(1);
    expect(container.querySelector("thead th")?.textContent).toBe("a");
  });

  it("renders inline formatting inside cells", () => {
    const md = "| k | v |\n|---|---|\n| **best** | `mae` |";
    const { container } = render(<>{renderMarkdown(md)}</>);
    const tds = container.querySelectorAll("tbody td");
    expect(tds[0].querySelector("strong")?.textContent).toBe("best");
    expect(tds[1].querySelector("code")?.textContent).toBe("mae");
  });

  it("renders a table followed by a blank-line-separated paragraph", () => {
    const { container } = render(<>{renderMarkdown(`${TABLE_MD}\n\nAnd the verdict.`)}</>);
    expect(container.querySelector("table")).not.toBeNull();
    const ps = [...container.querySelectorAll("p")].map((el) => el.textContent);
    expect(ps).toContain("And the verdict.");
  });

  it("keeps non-table pipe text as a paragraph", () => {
    const { container } = render(<>{renderMarkdown("a | b | c with no separator")}</>);
    expect(container.querySelector("table")).toBeNull();
    expect(container.querySelector("p")?.textContent).toContain("a | b | c");
  });

  it("treats rows without pipes after the separator as end of table", () => {
    const md = "| a |\n|---|\n| 1 |\ntrailing line without pipes";
    const { container } = render(<>{renderMarkdown(md)}</>);
    expect(container.querySelectorAll("tbody tr")).toHaveLength(1);
  });
});

describe("renderMarkdown fenced code", () => {
  it("renders a ```mermaid fence via MermaidDiagram into a wrapped svg", async () => {
    const md = "```mermaid\ngraph TD; A-->B;\n```";
    const { container } = render(<>{renderMarkdown(md)}</>);
    expect(container.querySelector(".mermaid-wrap")).not.toBeNull();
    await waitFor(() =>
      expect(container.querySelector('.mermaid-host svg[data-mock="mermaid-svg"]')).not.toBeNull(),
    );
  });

  it("renders other languages as styled pre/code", () => {
    const md = "```python\nprint('hi')\n```";
    const { container } = render(<>{renderMarkdown(md)}</>);
    const pre = container.querySelector("pre.code-block")!;
    expect(pre).not.toBeNull();
    expect(pre.querySelector("code")?.textContent).toBe("print('hi')");
    expect(container.querySelector(".mermaid-wrap")).toBeNull();
  });

  it("renders a fence without a language as pre/code", () => {
    const md = "```\njust text\n```";
    const { container } = render(<>{renderMarkdown(md)}</>);
    expect(container.querySelector("pre.code-block code")?.textContent).toBe("just text");
  });

  it("keeps blank lines inside a fence as one code block", () => {
    const md = "```\nline1\n\nline2\n```";
    const { container } = render(<>{renderMarkdown(md)}</>);
    const pres = container.querySelectorAll("pre.code-block");
    expect(pres).toHaveLength(1);
    expect(pres[0].textContent).toBe("line1\n\nline2");
  });

  it("keeps document ordering: paragraph, list, fence, table", () => {
    const md = [
      "Intro paragraph.",
      "",
      "- item a",
      "- item b",
      "",
      "```json",
      '{"k": 1}',
      "```",
      "",
      "| a |",
      "|---|",
      "| 1 |",
    ].join("\n");
    const { container } = render(<>{renderMarkdown(md)}</>);
    const kids = [...container.children];
    expect(kids[0].tagName).toBe("P");
    expect(kids[1].tagName).toBe("UL");
    expect(kids[2].tagName).toBe("PRE");
    expect(kids[2].querySelector("code")?.textContent).toBe('{"k": 1}');
    // tables render inside the shared scroll wrapper with the data-table class
    expect(kids[3].classList.contains("table-scroll")).toBe(true);
    expect(kids[3].querySelector("table.data-table")).not.toBeNull();
  });
});

describe("renderMarkdown list variants", () => {
  it("renders `*` bullets exactly like `-` bullets", () => {
    const { container } = render(<>{renderMarkdown("* one\n* two")}</>);
    const items = container.querySelectorAll("ul li");
    expect(items).toHaveLength(2);
    expect(items[0].textContent).toBe("one");
  });

  it("renders paren ordered lists (1) 2)) as ol", () => {
    const { container } = render(<>{renderMarkdown("1) first\n2) second")}</>);
    const items = container.querySelectorAll("ol li");
    expect(items).toHaveLength(2);
    expect(items[1].textContent).toBe("second");
  });
});

describe("renderMarkdown wrapped lists and thematic breaks", () => {
  it("joins an indented continuation line into the previous bullet as one <li>", () => {
    const md = [
      "- **Real track — UCI Online Retail II** (implemented; run with",
      "  `--data-source uci`):",
      "- second bullet stays its own item",
    ].join("\n");
    const { container } = render(<>{renderMarkdown(md)}</>);
    const items = container.querySelectorAll("ul li");
    expect(items).toHaveLength(2);
    expect(items[0].textContent).toBe(
      "Real track — UCI Online Retail II (implemented; run with --data-source uci):",
    );
    // inline bold and code formatting work in the joined continuation
    expect(items[0].querySelector("strong")?.textContent).toBe("Real track — UCI Online Retail II");
    expect(items[0].querySelector("code")?.textContent).toBe("--data-source uci");
    expect(items[1].textContent).toBe("second bullet stays its own item");
  });

  it("joins continuation lines indented deeper than 2 spaces (YAML-aligned wraps)", () => {
    const md = "- first item\n        deeply indented wrap line\n- second item";
    const { container } = render(<>{renderMarkdown(md)}</>);
    const items = container.querySelectorAll("ul li");
    expect(items).toHaveLength(2);
    expect(items[0].textContent).toBe("first item deeply indented wrap line");
  });

  it("splits a list followed by an unindented non-item line into list + paragraph", () => {
    const md = "- item one\n- item two\nNew paragraph after the list.";
    const { container } = render(<>{renderMarkdown(md)}</>);
    const ul = container.querySelector("ul");
    expect(ul).not.toBeNull();
    expect(ul!.querySelectorAll("li")).toHaveLength(2);
    const ps = container.querySelectorAll("p");
    expect(ps).toHaveLength(1);
    expect(ps[0].textContent).toBe("New paragraph after the list.");
  });

  it("renders ---, *** and ___ lines as <hr class='md-break'>", () => {
    const { container } = render(<>{renderMarkdown("above\n\n---\n\nbelow")}</>);
    const hr = container.querySelector("hr.md-break");
    expect(hr).not.toBeNull();
    expect(container.querySelector("p")?.textContent).toBe("above");
    expect(container.querySelectorAll("p")[1]?.textContent).toBe("below");
    for (const tok of ["***", "___"]) {
      const c = render(<>{renderMarkdown(`${tok}`)}</>);
      expect(c.container.querySelectorAll("hr.md-break")).toHaveLength(1);
    }
  });

  it("renders ordered-list continuations the same way", () => {
    const md = "1. first step wraps\n   onto the next line\n2. second step";
    const { container } = render(<>{renderMarkdown(md)}</>);
    const items = container.querySelectorAll("ol li");
    expect(items).toHaveLength(2);
    expect(items[0].textContent).toBe("first step wraps onto the next line");
  });

  it("does not treat a non-item first line as a list", () => {
    const { container } = render(<>{renderMarkdown("dashes - inside a paragraph stay text")}</>);
    expect(container.querySelector("ul")).toBeNull();
    expect(container.querySelector("p")?.textContent).toContain("dashes - inside a paragraph");
  });
});

describe("prose density (wave 10)", () => {
  const css = readFileSync("src/styles.css", "utf8");

  it("keeps the story prose as wide as the figures (no 70ch cap on .story-main)", () => {
    expect(css).not.toMatch(/\.story-main\s*\{[^}]*max-width:\s*70ch/);
    // section padding/typography rhythm untouched
    expect(css).toContain(".story-section .prose {\n  line-height: 1.62;\n}");
  });

  it("ships the typography-rhythm hooks (line-height, spacing, markers)", () => {
    expect(css).toContain(".story-section .prose {\n  line-height: 1.62;\n}");
    expect(css).toContain(".story-section .prose p {\n  margin: 0 0 1.05em;\n}");
    expect(css).toContain("padding-left: 1.5rem;");
    expect(css).toContain(".story-section .prose li {\n  margin-bottom: 0.4rem;\n}");
    expect(css).toContain(".story-section .prose li::marker {\n  color: var(--accent);\n}");
    // air after a paragraph that introduces a list/table/code/diagram
    expect(css).toContain(".story-section .prose p + ul,");
    expect(css).toContain("margin-top: 1.3rem;");
  });

  it("keeps dense documents structured (paragraph → list → table sequence intact)", () => {
    const dense = [
      "The evaluation compares four model families across five folds.",
      "",
      "- **GBDT** tuned with Optuna, early stopping on",
      "- a **naive seasonal** baseline, and",
      "- a linear model as the sanity check",
      "",
      "| run | mae |",
      "|---|---|",
      "| gbm | 412.3 |",
      "| naive | 587.1 |",
    ].join("\n");
    const { container } = render(
      <MemoryRouter>
        <div className="story-section">
          <div className="prose">{renderMarkdown(dense)}</div>
        </div>
      </MemoryRouter>,
    );
    const kids = [...container.querySelector(".prose")!.children];
    expect(kids[0].tagName).toBe("P");
    expect(kids[1].tagName).toBe("UL");
    expect(kids[1].querySelectorAll("li")).toHaveLength(3);
    expect(kids[1].querySelector("strong")?.textContent).toBe("GBDT");
    expect(kids[2].classList.contains("table-scroll")).toBe(true);
    expect(kids[2].querySelector("tbody tr")).not.toBeNull();
  });
});

describe("renderMarkdown glossary auto-linking", () => {
  function renderWithRouter(md: string, linked?: Set<string>) {
    return render(<MemoryRouter>{renderMarkdown(md, linked)}</MemoryRouter>);
  }

  it("links the first occurrence of a term to /glossary#slug", () => {
    const { container } = renderWithRouter(
      "The holdout estimates generalization; a second holdout mention stays plain.",
    );
    const links = container.querySelectorAll("a.glossary-term");
    expect(links).toHaveLength(1);
    expect(links[0].getAttribute("href")).toBe("/glossary#holdout");
    expect(links[0].textContent).toContain("holdout");
    expect(container.textContent).toContain("a second holdout mention stays plain.");
  });

  it("links terms inside bold and emphasis without losing formatting", () => {
    const { container } = renderWithRouter(
      "A **baseline model** and an *honest baseline* both link.",
    );
    const links = container.querySelectorAll("a.glossary-term");
    expect(links).toHaveLength(1);
    expect(links[0].childNodes[0].textContent).toBe("baseline");
    expect(links[0].closest("strong")?.textContent).toContain(" model");
    expect(container.querySelector("em")?.textContent).toContain("honest baseline");
    expect(container.querySelector("em a.glossary-term")).toBeNull();
  });

  it("matches case-insensitively and respects word boundaries", () => {
    const { container } = renderWithRouter(
      "wape and MASE are metrics; MASEs and baselines are not linked.",
    );
    const hrefs = [...container.querySelectorAll("a.glossary-term")].map((a) =>
      a.getAttribute("href"),
    );
    expect(hrefs).toEqual(["/glossary#wape", "/glossary#mase"]);
    // plural/inflected forms and the rest of the sentence stay plain text
    expect(container.textContent).toContain("MASEs and baselines are not linked.");
    expect(container.querySelector("code")).toBeNull();
  });

  it("links multi-word terms whole (longest first) and never inside code", () => {
    const md =
      "A `confidence interval` in code stays plain; a real confidence interval links; " +
      "so does p50/p95 latency.";
    const { container } = renderWithRouter(md);
    const hrefs = [...container.querySelectorAll("a.glossary-term")].map((a) =>
      a.getAttribute("href"),
    );
    expect(hrefs).toEqual(["/glossary#confidence-interval", "/glossary#p50-p95-latency"]);
    expect(container.querySelector("code")?.textContent).toBe("confidence interval");
  });

  it("never links terms inside fenced code blocks", () => {
    const md = "```\nbaseline\n```\n\nThe baseline model links.";
    const { container } = renderWithRouter(md);
    const links = container.querySelectorAll("a.glossary-term");
    expect(links).toHaveLength(1);
    expect(links[0].getAttribute("href")).toBe("/glossary#baseline");
    expect(container.querySelector("pre.code-block")?.textContent).toContain("baseline");
  });

  it("treats an externally threaded Set as an allow-list without mutation", () => {
    const linked = new Set<string>(["baseline"]);
    const first = renderWithRouter("A baseline model.", linked);
    expect(first.container.querySelectorAll("a.glossary-term")).toHaveLength(1);
    const second = renderWithRouter("Back to the baseline again.", linked);
    expect(second.container.querySelectorAll("a.glossary-term")).toHaveLength(1);
    expect(linked.size).toBe(1); // renderers never mutate caller-owned state
  });

  it("links glossary terms without any tooltip popup (definitions live in the Background card)", () => {
    const { container } = renderWithRouter("Calibration matters more than raw accuracy.");
    const link = container.querySelector("a.glossary-term")!;
    expect(link.getAttribute("href")).toBe("/glossary#calibration");
    expect(link.textContent).toBe("Calibration");
    expect(link.querySelector(".glossary-tip")).toBeNull();
    expect(container.querySelectorAll('[role="tooltip"]')).toHaveLength(0);
  });
});
