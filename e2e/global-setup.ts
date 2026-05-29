import { execSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

async function waitForUrl(url: string, timeoutMs = 60_000): Promise<void> {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    try {
      const response = await fetch(url);
      if (response.ok) {
        return;
      }
    } catch {
      // retry
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error(`Timed out waiting for ${url}`);
}

export default async function globalSetup(): Promise<void> {
  if (process.env.SKIP_E2E_SETUP === "1") {
    return;
  }

  if (process.env.CI) {
    execSync(
      `docker run -d --rm --name wiremock-e2e -p 8089:8080 \
        -v "${ROOT}/e2e/wiremock:/home/wiremock" \
        wiremock/wiremock:3.9.1 --global-response-templating`,
      { stdio: "inherit" },
    );
  } else {
    execSync(
      "docker compose -f docker-compose.yml -f docker-compose.e2e.yml up -d postgres redis wiremock",
      { cwd: ROOT, stdio: "inherit" },
    );
  }

  await waitForUrl("http://127.0.0.1:8089/__admin/health");

  const venvPython = path.join(ROOT, ".venv/bin/python");
  execSync(`${venvPython} -m alembic upgrade head`, {
    cwd: path.join(ROOT, "apps/api"),
    env: {
      ...process.env,
      DATABASE_URL_SYNC:
        process.env.DATABASE_URL_SYNC ??
        "postgresql://techsupport:techsupport@localhost:5433/techsupport",
    },
    stdio: "inherit",
  });
}
