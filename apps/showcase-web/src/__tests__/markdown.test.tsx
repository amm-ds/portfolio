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
