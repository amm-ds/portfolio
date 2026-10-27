import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/testSetup.ts",
    css: false,
    // jsdom worker startup alone measures ~4s on this repo; the default 5s
    // per-test timeout flakes on loaded machines (CI runners are fine).
    testTimeout: 30000,
  },
});
