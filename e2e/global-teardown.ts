import { execSync } from "node:child_process";

export default async function globalTeardown(): Promise<void> {
  if (process.env.CI !== "true") {
    return;
  }

  try {
    execSync("docker stop wiremock-e2e", { stdio: "ignore" });
  } catch {
    // container may already be gone
  }
}
