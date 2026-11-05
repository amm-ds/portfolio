import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { FlowDiagram } from "../components/diagrams/FlowDiagram";
import { AGENT_LOOP_SPEC, ROUTING_SPEC } from "../diagrams";

class ResizeObserverMock {
  constructor(private callback: ResizeObserverCallback) {}
  observe(target: Element) {
    queueMicrotask(() => {
      const entry = { target, contentRect: target.getBoundingClientRect() } as ResizeObserverEntry;
      this.callback([entry], this as unknown as ResizeObserver);
    });
  }
  unobserve() {}
  disconnect() {}
}

class DOMMatrixReadOnlyMock {
  m22 = 1;
  constructor(transform = "") {
    const scale = /scale\(([\d.]+)\)/.exec(transform);
    if (scale) this.m22 = Number(scale[1]);
  }
}

beforeEach(() => {
  vi.stubGlobal("ResizeObserver", ResizeObserverMock);
  vi.stubGlobal("DOMMatrixReadOnly", DOMMatrixReadOnlyMock);
  // jsdom has no layout: expose stable dimensions so v12 can measure nodes and
  // run the same post-measure dagre path used by the browser.
  Object.defineProperties(HTMLElement.prototype, {
    offsetWidth: { configurable: true, get: () => 196 },
    offsetHeight: { configurable: true, get: () => 82 },
    clientWidth: { configurable: true, get: () => 1000 },
    clientHeight: { configurable: true, get: () => 520 },
    getBoundingClientRect: {
      configurable: true,
      value: function (this: HTMLElement) {
        const isNode = this.classList.contains("react-flow__node");
        const width = isNode ? 196 : 1000;
        const height = isNode ? 82 : 520;
        return { x: 0, y: 0, top: 0, left: 0, right: width, bottom: height, width, height, toJSON: () => ({}) };
      },
    },
  });
  Object.defineProperty(SVGElement.prototype, "getBBox", {
    configurable: true,
    value: () => ({ x: 0, y: 0, width: 100, height: 14 }),
  });
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("FlowDiagram", () => {
  it.each([
    ["09 agent loop", AGENT_LOOP_SPEC, "Plan · typed steps + calls"],
    ["04 routing", ROUTING_SPEC, "TF-IDF + logistic regression"],
  ])("renders the %s pilot spec", async (_name, spec, label) => {
    render(<FlowDiagram spec={spec} />);
    expect(await screen.findByText(label)).toBeInTheDocument();
    await waitFor(() => expect(document.querySelector(".frame-skeleton")).toBeNull());
    const positions = [...document.querySelectorAll(".react-flow__node")].map((node) =>
      (node as HTMLElement).style.transform,
    );
    expect(new Set(positions).size).toBeGreaterThan(1);
    expect(document.querySelector(".react-flow__minimap")).toBeNull();
    expect(screen.getByRole("button", { name: /zoom in/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /fit view/i })).toBeInTheDocument();
  });

  it("opens the inspector with the clicked node's committed facts", async () => {
    render(<FlowDiagram spec={AGENT_LOOP_SPEC} />);
    const node = await screen.findByTestId("rf__node-plan");
    fireEvent.click(node);
    const inspector = await screen.findByRole("complementary", { name: "Facts for Plan · typed steps + calls" });
    expect(inspector).toHaveTextContent("400 requests and 4,000,000 total tokens per suite");
    expect(inspector).toHaveTextContent("whitelisted toolset");
  });

  it("closes the inspector via its close button and clears the canvas selection", async () => {
    render(<FlowDiagram spec={AGENT_LOOP_SPEC} />);
    fireEvent.click(await screen.findByTestId("rf__node-plan"));
    await screen.findByRole("complementary", { name: "Facts for Plan · typed steps + calls" });
    fireEvent.click(screen.getByRole("button", { name: "Close inspector" }));
    expect(
      screen.queryByRole("complementary", { name: "Facts for Plan · typed steps + calls" }),
    ).toBeNull();
    // the node must not keep its selection ring, or re-clicking never re-fires
    expect(document.querySelector(".react-flow__node.selected")).toBeNull();
  });

  it("gives every node a focusable, labelled button and supports keyboard inspection", async () => {
    render(<FlowDiagram spec={ROUTING_SPEC} />);
    for (const specNode of ROUTING_SPEC.nodes) {
      const node = await screen.findByTestId(`rf__node-${specNode.id}`);
      expect(node).toHaveAttribute("tabindex", "0");
      expect(node).toHaveAttribute("role", "button");
      expect(node).toHaveAccessibleName(expect.stringContaining(specNode.label));
    }
    const gate = screen.getByTestId("rf__node-gate");
    const description = document.getElementById(gate.getAttribute("aria-describedby") ?? "");
    expect(description).toHaveTextContent("Press enter or space to inspect a node");
    expect(description).not.toHaveTextContent("delete");
    fireEvent.keyDown(gate, { key: "Enter" });
    await waitFor(() => expect(screen.getByRole("complementary", { name: /Facts for Confidence gate/ })).toBeInTheDocument());
    expect(screen.getByText(/24.6% of items escalate/)).toBeInTheDocument();
  });
});
