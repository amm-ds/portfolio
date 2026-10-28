import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In dev, proxy API paths to the FastAPI app; in prod FastAPI serves dist/.
// /demos and /projects are shared namespaces: the bare paths and single-id
// segments (/projects/<pid>, /demos is API-only except known SPA routes) are
// client-side page routes, everything with a resource subpath is API.
const DEMO_API = /^\/demos\/[^/]+\/(manifest|payload|replay|live)(\/|$)/;
const PROJECT_PAGE = /^\/projects\/\d{2}-[^/]+$/;
export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 4321,
    proxy: {
      "/projects": {
        target: "http://127.0.0.1:8000",
        bypass: (req) => {
          const url = req.url ?? "";
          // deep links like /projects/02-demand-forecasting are SPA page
          // routes (the API only serves /projects/<pid>/<resource>); the bare
          // /projects list is API JSON unless the browser asks for a page
          if (PROJECT_PAGE.test(url)) return url;
          if (url === "/projects" && !(req.headers.accept ?? "").includes("text/html"))
            return undefined; // JSON list → API
          if (url === "/projects") return url; // page navigation → SPA
          return undefined; // /projects/<pid>/<resource> → API
        },
      },
      "/rag": "http://127.0.0.1:8000",
      "/health": "http://127.0.0.1:8000",
      "/demos": {
        target: "http://127.0.0.1:8000",
        bypass: (req) => {
          const url = req.url ?? "";
          if (url === "/demos" || DEMO_API.test(url)) return undefined; // proxy
          return url; // SPA page route — serve from vite
        },
      },
    },
  },
});
