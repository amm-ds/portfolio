import "@testing-library/jest-dom/vitest";

// jsdom does not implement scrolling; route-focus tests cover the call itself.
Object.defineProperty(window, "scrollTo", { value: () => {}, writable: true });
