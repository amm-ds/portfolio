import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In dev, proxy API paths to the FastAPI app; in prod FastAPI serves dist/.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/projects": "http://localhost:8000",
      "/rag": "http://localhost:8000",
      "/health": "http://localhost:8000",
    },
  },
});
