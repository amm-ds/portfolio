import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { renderMarkdown } from "../lib/markdown";

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
