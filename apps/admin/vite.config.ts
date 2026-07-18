import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");

function resolveApiProxyTarget(mode: string): string {
  const fromEnvFile = loadEnv(mode, repoRoot, "").API_PROXY_TARGET;
  const fromProcess = process.env.API_PROXY_TARGET;
  return fromEnvFile || fromProcess || "http://localhost:8000";
}

export default defineConfig(({ mode }) => {
  const apiTarget = resolveApiProxyTarget(mode);

  return {
    plugins: [react()],
    envDir: repoRoot,
    server: {
      port: 5174,
      host: true,
      proxy: {
        "/api": {
          target: apiTarget,
          changeOrigin: true,
        },
        "/health": {
          target: apiTarget,
          changeOrigin: true,
        },
      },
    },
  };
});
