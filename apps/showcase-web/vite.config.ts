import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In dev, proxy API paths to the FastAPI app; in prod FastAPI serves dist/.
// /demos is shared: /demos (registry) and /demos/<id>/(manifest|payload) are
// API, but /demos/<id> itself is a client-side page route — bypass those.
const DEMO_API = /^\/demos\/[^/]+\/(manifest|payload|replay|live)(\/|$)/;
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/projects": "http://localhost:8000",
      "/rag": "http://localhost:8000",
      "/health": "http://localhost:8000",
      "/demos": {
        target: "http://localhost:8000",
        bypass: (req) => {
          const url = req.url ?? "";
          if (url === "/demos" || DEMO_API.test(url)) return undefined; // proxy
          return url; // SPA page route — serve from vite
        },
      },
    },
  },
});
