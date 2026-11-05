import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// The backend's default port is 8000 (see apps/agent-chat/README.md quickstart
// and infra/docker-compose.yml); override with VITE_API_BASE for remote APIs.
const backend = process.env.VITE_API_PROXY_TARGET ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 4322,
    proxy: {
      "/chat": backend,
      "/conversations": backend,
      "/approvals": backend,
      "/health": backend,
      "/ready": backend,
      "/ingest": backend,
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/test/setup.ts",
    css: false,
    exclude: ["e2e/**", "node_modules/**", "dist/**"],
  },
});
