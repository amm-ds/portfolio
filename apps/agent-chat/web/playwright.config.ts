import { defineConfig } from "playwright/test";

// Smoke-only e2e config: boots the dev server (mock transport) and checks the
// shell renders. Run `npm run test:e2e` after `npx playwright install`.
export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  use: {
    baseURL: "http://localhost:4322",
  },
  webServer: {
    command: "npm run dev",
    url: "http://localhost:4322",
    reuseExistingServer: !process.env.CI,
    env: { VITE_MOCK: "1" },
  },
});
