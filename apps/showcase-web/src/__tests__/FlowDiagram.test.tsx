import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { FlowDiagram } from "../components/diagrams/FlowDiagram";
import { AGENT_LOOP_SPEC, getDiagramSpec, RAG_PIPELINE_SPEC, ROUTING_SPEC } from "../diagrams";

class ResizeObserverMock {
  constructor(private callback: ResizeObserverCallback) {}
  observe(target: Element) {
    queueMicrotask(() => {
      const rect = target.getBoundingClientRect();
      const entry = {
        target,
        contentRect: { ...rect, width: target.clientWidth, height: target.clientHeight },
      } as ResizeObserverEntry;
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

  it("removes fact-selection prompts and hugs a single-rank canvas", async () => {
    render(<FlowDiagram spec={ROUTING_SPEC} />);
    await waitFor(() => expect(document.querySelector(".frame-skeleton")).toBeNull());
    expect(screen.getByText("Full diagram shown · drag to pan · use controls to zoom")).toBeInTheDocument();
    expect(screen.queryByText(/select for/i)).toBeNull();
    expect(document.querySelector(".flow-node__action")).toBeNull();
    expect(document.querySelector(".flow-diagram__hint")).toBeNull();
    expect(document.querySelector(".flow-diagram__canvas")).toHaveStyle({ height: "240px" });
  });

  it("opens narrow canvases on a readable vertical diagram", async () => {
    Object.defineProperty(HTMLElement.prototype, "clientWidth", {
      configurable: true,
      get(this: HTMLElement) {
        return this.classList.contains("flow-diagram__canvas") ? 390 : 1000;
      },
    });
    render(<FlowDiagram spec={AGENT_LOOP_SPEC} />);
    await waitFor(() => expect(document.querySelector(".frame-skeleton")).toBeNull());

    const viewport = document.querySelector<HTMLElement>(".react-flow__viewport")!;
    const scale = /scale\(([\d.]+)\)/.exec(viewport.style.transform)?.[1];
    expect(scale).toBeDefined();
    // Narrow canvases keep full-size labels (zoom 1) and pan instead of
    // shrinking dense graphs until labels collide.
    expect(Number(scale)).toBe(1);
    expect(document.querySelector<HTMLElement>(".flow-diagram__canvas")!.style.height).not.toBe("240px");
    expect(document.querySelectorAll(".react-flow__node")).toHaveLength(AGENT_LOOP_SPEC.nodes.length);
    for (const node of AGENT_LOOP_SPEC.nodes) {
      expect(screen.getByTestId(`rf__node-${node.id}`)).toHaveAttribute("tabindex", "0");
    }
  });

  it("previews the hovered node's first fact and hides it behind the inspector", async () => {
    render(<FlowDiagram spec={AGENT_LOOP_SPEC} />);
    const node = await screen.findByTestId("rf__node-plan");
    fireEvent.mouseEnter(node);
    expect(await screen.findByRole("tooltip")).toHaveTextContent(AGENT_LOOP_SPEC.nodes[1].facts[0]);

    fireEvent.click(node);
    await screen.findByRole("complementary", { name: "Facts for Plan · typed steps + calls" });
    await waitFor(() => expect(screen.queryByRole("tooltip")).toBeNull());
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
      expect(node).toHaveAccessibleName(`${specNode.kind} ${specNode.label}`);
    }
    const gate = screen.getByTestId("rf__node-gate");
    const description = document.getElementById(gate.getAttribute("aria-describedby") ?? "");
    expect(description).toHaveTextContent("Press enter or space to inspect a node");
    expect(description).not.toHaveTextContent("delete");
    fireEvent.keyDown(gate, { key: "Enter" });
    await waitFor(() => expect(screen.getByRole("complementary", { name: /Facts for Confidence gate/ })).toBeInTheDocument());
    expect(screen.getByText(/24.6% of items escalate/)).toBeInTheDocument();
    fireEvent.keyDown(gate, { key: "Escape" });
    expect(screen.queryByRole("complementary", { name: /Facts for Confidence gate/ })).toBeNull();
    fireEvent.keyDown(gate, { key: " " });
    await waitFor(() => expect(screen.getByRole("complementary", { name: /Facts for Confidence gate/ })).toBeInTheDocument());
    fireEvent.keyDown(gate, { key: "Escape" });
    expect(screen.queryByRole("complementary", { name: /Facts for Confidence gate/ })).toBeNull();
  });

  it("draws every agent connection with explicit, distinct self-loops", async () => {
    render(<FlowDiagram spec={AGENT_LOOP_SPEC} />);
    await waitFor(() => expect(document.querySelector(".frame-skeleton")).toBeNull());

    const paths = [...document.querySelectorAll(".flow-edge__path")].map((path) => path.getAttribute("d"));
    expect(paths).toHaveLength(AGENT_LOOP_SPEC.edges.length);
    expect(new Set(paths).size).toBe(AGENT_LOOP_SPEC.edges.length);
    expect(screen.getByText("park / resume")).toBeInTheDocument();
    expect(screen.getByText("repair within cap")).toBeInTheDocument();
  });

  it("separates reciprocal edge labels instead of clipping or stacking them", async () => {
    render(<FlowDiagram spec={RAG_PIPELINE_SPEC} />);
    await waitFor(() => expect(document.querySelector(".frame-skeleton")).toBeNull());

    const forward = screen.getByText("draft + citations");
    const repair = screen.getByText("repair ≤ 2");
    expect(forward.style.transform).not.toBe(repair.style.transform);
    expect(document.querySelectorAll(".flow-edge__label")).toHaveLength(RAG_PIPELINE_SPEC.edges.length);
    expect(document.querySelector(".flow-edge__label-host")).toBeNull();
  });

  it("applies lit, dim, and pinned state directly to portaled labels", async () => {
    render(<FlowDiagram spec={AGENT_LOOP_SPEC} />);
    const plan = await screen.findByTestId("rf__node-plan");
    fireEvent.mouseEnter(plan);
    await waitFor(() => expect(screen.getByText("routine")).toHaveClass("is-lit"));
    expect(screen.getByText("park / resume")).toHaveClass("is-dim");
    fireEvent.mouseLeave(plan);
    await waitFor(() => expect(screen.getByText("routine")).not.toHaveClass("is-lit"));

    const feedback = document.querySelector<SVGGElement>('[data-id="checkpoint-plan"]')!;
    fireEvent.click(feedback);
    await waitFor(() => expect(screen.getByText("reject + feedback")).toHaveClass("is-pinned"));
    fireEvent.keyDown(feedback, { key: "Escape" });
    expect(screen.getByText("reject + feedback")).not.toHaveClass("is-pinned");
  });

  it("keeps highlight-only auto nodes and read-only edges out of the tab order", async () => {
    const spec = getDiagramSpec("auto-09-agentic-workflows-4");
    expect(spec).toBeDefined();
    if (!spec) return;
    render(<FlowDiagram spec={spec} />);
    await waitFor(() => expect(document.querySelector(".frame-skeleton")).toBeNull());
    for (const specNode of spec.nodes) {
      const node = screen.getByTestId(`rf__node-${specNode.id}`);
      expect(node).toHaveAttribute("role", "group");
      expect(node).toHaveAccessibleName(`${specNode.kind} ${specNode.label}`);
      expect(node).not.toHaveAttribute("tabindex", "0");
    }
    for (const edge of document.querySelectorAll(".react-flow__edge")) {
      expect(edge).not.toHaveAttribute("tabindex", "0");
    }
  });

  it("names edges with kind, label, and endpoint labels and distinguishes kinds by dash", async () => {
    render(<FlowDiagram spec={RAG_PIPELINE_SPEC} />);
    await waitFor(() => expect(document.querySelector(".frame-skeleton")).toBeNull());
    const result = document.querySelector<SVGGElement>('[data-id="draft-verifier"]')!;
    expect(result).toHaveAccessibleName(
      'result edge “draft + citations”: Agent draft with citations to Claim verifier · 0.6 support floor',
    );
    expect(result.querySelector<SVGPathElement>(".flow-edge__path")!.style.strokeDasharray).toBe("8 4");
    const task = document.querySelector<SVGGElement>('[data-id="funnel-draft"]')!;
    expect(task.querySelector<SVGPathElement>(".flow-edge__path")!.style.strokeDasharray).toBe("");
    const error = document.querySelector<SVGGElement>('[data-id="verifier-draft"]')!;
    expect(error.querySelector<SVGPathElement>(".flow-edge__path")!.style.strokeDasharray).toBe("2 5");
  });

  it("distributes shared source and target connections across distinct handles", async () => {
    render(<FlowDiagram spec={AGENT_LOOP_SPEC} />);
    const execute = await screen.findByTestId("rf__node-execute");
    const sources = [...execute.querySelectorAll<HTMLElement>(".react-flow__handle.source")];
    expect(sources).toHaveLength(AGENT_LOOP_SPEC.edges.filter((edge) => edge.source === "execute").length);
    expect(new Set(sources.map((handle) => handle.style.top)).size).toBe(sources.length);
    const critique = screen.getByTestId("rf__node-critique");
    const targets = [...critique.querySelectorAll<HTMLElement>(".react-flow__handle.target")];
    expect(targets).toHaveLength(AGENT_LOOP_SPEC.edges.filter((edge) => edge.target === "critique").length);
    expect(new Set(targets.map((handle) => handle.style.top)).size).toBe(targets.length);
  });

  it("preserves a user-adjusted viewport when the canvas resizes", async () => {
    let width = 390;
    const callbacks = new Set<ResizeObserverCallback>();
    class ControlledResizeObserver {
      constructor(callback: ResizeObserverCallback) {
        callbacks.add(callback);
      }
      observe(target: Element) {
        queueMicrotask(() => {
          const entry = {
            target,
            contentRect: { width: target.clientWidth, height: target.clientHeight },
          } as ResizeObserverEntry;
          for (const callback of callbacks) {
            callback([entry], {} as ResizeObserver);
          }
        });
      }
      unobserve() {}
      disconnect() {}
    }
    vi.stubGlobal("ResizeObserver", ControlledResizeObserver);
    Object.defineProperty(HTMLElement.prototype, "clientWidth", {
      configurable: true,
      get(this: HTMLElement) {
        return this.classList.contains("flow-diagram__canvas") ? width : 1000;
      },
    });
    render(<FlowDiagram spec={AGENT_LOOP_SPEC} />);
    await waitFor(() => expect(document.querySelector(".frame-skeleton")).toBeNull());
    const viewport = document.querySelector<HTMLElement>(".react-flow__viewport")!;
    fireEvent.click(screen.getByRole("button", { name: /zoom in/i }));
    await waitFor(() => expect(viewport.style.transform).not.toContain("scale(1)"));
    const adjusted = viewport.style.transform;

    const canvas = document.querySelector<HTMLElement>(".flow-diagram__canvas")!;
    await act(async () => {
      width = 700;
      for (const callback of callbacks) {
        callback(
          [{ target: canvas, contentRect: { width, height: 520 } } as unknown as ResizeObserverEntry],
          {} as ResizeObserver,
        );
      }
      await new Promise((resolve) => setTimeout(resolve, 20));
    });
    expect(viewport.style.transform).toBe(adjusted);
  });
});
