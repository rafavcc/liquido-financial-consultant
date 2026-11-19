import { defineConfig, devices } from "@playwright/test";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const PORT = 8765;
// banco descartável: o e2e nunca toca em backend/data/liquido.db
const dbDir = mkdtempSync(join(tmpdir(), "liquido-e2e-"));

// pré-requisito: `npm run build` (o backend serve frontend/dist)
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 60_000,
  reporter: "list",
  use: { baseURL: `http://127.0.0.1:${PORT}`, trace: "off" },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] }, testIgnore: /mobile\.spec\.ts/ },
    { name: "iphone", use: { ...devices["iPhone 13"], defaultBrowserType: "chromium" }, testMatch: /mobile\.spec\.ts/ },
  ],
  webServer: {
    command: `uv run --directory ../backend uvicorn app.main:app --host 127.0.0.1 --port ${PORT}`,
    url: `http://127.0.0.1:${PORT}/api/health`,
    reuseExistingServer: false,
    timeout: 60_000,
    env: {
      LIQUIDO_MARKET_FIXTURES: join(process.cwd(), "..", "backend", "tests", "fixtures", "market"),
      LIQUIDO_DB: join(dbDir, "liquido.db"),
      LIQUIDO_STATIC_DIR: join(process.cwd(), "dist"),
    },
  },
});
