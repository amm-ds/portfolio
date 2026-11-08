import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const backend = process.env.VITE_API_PROXY_TARGET ?? "http://localhost:8001";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 4323,
    proxy: {
      "/documents": backend,
      "/health": backend,
      "/ready": backend,
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes("node_modules/pdfjs-dist")) return "pdfjs";
          if (id.includes("node_modules/react")) return "react-vendor";
        },
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/test/setup.ts",
    css: false,
    exclude: ["e2e/**", "node_modules/**", "dist/**", "artifacts/**"],
  },
});
