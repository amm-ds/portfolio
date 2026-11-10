import "@testing-library/jest-dom/vitest";

// jsdom does not implement scrolling; route-focus tests cover the call itself.
Object.defineProperty(window, "scrollTo", { value: () => {}, writable: true });

// jsdom has no ResizeObserver; @xyflow/react (and several chart effects) call
// it unconditionally in passive effects, which escapes to an uncaught error
// whenever a test renders a real FlowDiagram without stubbing it first (the
// intermittent App-routing failure). A silent no-op stub keeps jsdom tests
// deterministic; suites that need observation behavior stub their own
// implementation (vi.stubGlobal overrides this).
if (typeof globalThis.ResizeObserver === "undefined") {
  class ResizeObserverStub {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  vi.stubGlobal("ResizeObserver", ResizeObserverStub);
}
