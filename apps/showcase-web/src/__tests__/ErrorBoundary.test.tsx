import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DemoErrorBoundary } from "../demos/ErrorBoundary";

/** Test-only component that always throws during render. */
function Thrower(): never {
  throw new Error("boom");
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("DemoErrorBoundary", () => {
  it("renders its children when nothing throws", () => {
    render(
      <DemoErrorBoundary>
        <p>demo body</p>
      </DemoErrorBoundary>,
    );
    expect(screen.getByText("demo body")).toBeInTheDocument();
  });

  it("renders the fallback with a reload button and a back link when a child throws", () => {
    // the boundary logs the crash — silence the expected console noise
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    render(
      <DemoErrorBoundary>
        <Thrower />
      </DemoErrorBoundary>,
    );
    expect(screen.getByText("This demo hit an unexpected error.")).toBeInTheDocument();
    // reset button reloads the page
    expect(screen.getByRole("button", { name: "try again" })).toBeInTheDocument();
    // and a link leads back to the demos index
    expect(screen.getByRole("link", { name: "back to demos" })).toHaveAttribute(
      "href",
      "/projects#demos",
    );
    // the crashed child is replaced by the fallback, not rendered
    expect(screen.queryByText("demo body")).toBeNull();
  });
});
