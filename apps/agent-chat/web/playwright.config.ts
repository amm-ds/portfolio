import { defineConfig } from "playwright/test";

// Smoke-only e2e config: boots the dev server (mock transport) and checks the
// shell renders. Run `npm run test:e2e` after `npx playwright install`.
export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  use: {
    baseURL: "http://localhost:4399",
  },
  webServer: {
    command: "npm run dev -- --port 4399 --strictPort",
    url: "http://localhost:4399",
    // Never run mock-transport assertions against an unrelated existing app.
    reuseExistingServer: false,
    env: { VITE_MOCK: "1" },
  },
});
