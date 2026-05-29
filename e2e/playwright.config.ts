import { defineConfig, devices } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const API_PORT = process.env.E2E_API_PORT ?? "8010";
const WEB_PORT = process.env.E2E_WEB_PORT ?? "5174";
const API_URL = `http://127.0.0.1:${API_PORT}`;
const WEB_URL = `http://127.0.0.1:${WEB_PORT}`;

const apiEnv: Record<string, string> = {
  E2E_API_PORT: API_PORT,
  API_ENV: "test",
  API_HOST: "127.0.0.1",
  API_PORT,
  AUTH_MODE: "dev",
  GRAPH_ENABLED: "true",
  GRAPH_LLM_MODE: "mock",
  DATABASE_URL:
    process.env.DATABASE_URL ??
    "postgresql+asyncpg://techsupport:techsupport@localhost:5433/techsupport",
  DATABASE_URL_SYNC:
    process.env.DATABASE_URL_SYNC ??
    "postgresql://techsupport:techsupport@localhost:5433/techsupport",
  REDIS_URL: process.env.REDIS_URL ?? "redis://localhost:6380/0",
  ZAMMAD_BASE_URL: process.env.ZAMMAD_BASE_URL ?? "http://127.0.0.1:8089",
  ZAMMAD_API_TOKEN: process.env.ZAMMAD_API_TOKEN ?? "e2e-test-token",
  CORS_ORIGINS: `["${WEB_URL}","http://localhost:${WEB_PORT}"]`,
};

export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : [["list"], ["html"]],
  timeout: 60_000,
  expect: { timeout: 15_000 },
  globalSetup: path.join(path.dirname(fileURLToPath(import.meta.url)), "global-setup.ts"),
  globalTeardown: path.join(path.dirname(fileURLToPath(import.meta.url)), "global-teardown.ts"),
  use: {
    baseURL: WEB_URL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: [
    {
      command: `bash ${path.join(ROOT, "scripts/run_e2e_api.sh")}`,
      url: `${API_URL}/health/ready`,
      reuseExistingServer: false,
      timeout: 120_000,
      cwd: path.join(ROOT, "apps/api"),
      env: apiEnv,
    },
    {
      command: "npm run dev -- --port 5174 --strictPort",
      url: WEB_URL,
      reuseExistingServer: false,
      timeout: 120_000,
      cwd: path.join(ROOT, "apps/web"),
      env: {
        ...process.env,
        API_PROXY_TARGET: API_URL,
      },
    },
  ],
});
