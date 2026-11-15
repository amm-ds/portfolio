import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const backend = process.env.VITE_API_PROXY_TARGET ?? "http://localhost:8002";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 4324,
    proxy: {
      "/datasets": backend,
      "/runs": backend,
      "/health": backend,
      "/ready": backend,
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/test/setup.ts",
    css: false,
    exclude: ["node_modules/**", "dist/**", "artifacts/**"],
  },
});
