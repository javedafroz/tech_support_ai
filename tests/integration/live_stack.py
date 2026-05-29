"""Start/stop real API + web dev servers for browser-based live integration tests."""

from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]


class LiveStack:
    def __init__(self) -> None:
        self.api_port = os.environ.get("LIVE_API_PORT", "8020")
        self.web_port = os.environ.get("LIVE_WEB_PORT", "5175")
        self.api_url = f"http://127.0.0.1:{self.api_port}"
        self.web_url = f"http://127.0.0.1:{self.web_port}"
        self._processes: list[subprocess.Popen] = []

    def start(self) -> None:
        if self._processes:
            return

        api_env = os.environ.copy()
        api_env["E2E_API_PORT"] = self.api_port
        api_env["API_ENV"] = "test"
        api_env["CORS_ORIGINS"] = f'["{self.web_url}","http://localhost:{self.web_port}"]'

        api_script = ROOT / "scripts" / "run_e2e_api.sh"
        api_proc = subprocess.Popen(
            ["bash", str(api_script)],
            cwd=ROOT / "apps/api",
            env=api_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        self._processes.append(api_proc)
        self._wait_url(f"{self.api_url}/health/ready", name="API")

        web_env = os.environ.copy()
        web_env["API_PROXY_TARGET"] = self.api_url
        web_proc = subprocess.Popen(
            [
                "npm",
                "run",
                "dev",
                "--",
                "--port",
                self.web_port,
                "--strictPort",
                "--host",
                "127.0.0.1",
            ],
            cwd=ROOT / "apps/web",
            env=web_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        self._processes.append(web_proc)
        self._wait_url(self.web_url, name="Web UI")

    def stop(self) -> None:
        for proc in reversed(self._processes):
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGTERM)
        for proc in reversed(self._processes):
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
        self._processes.clear()

    def _wait_url(self, url: str, *, name: str, timeout_s: float = 120) -> None:
        deadline = time.time() + timeout_s
        last_error = ""
        while time.time() < deadline:
            try:
                response = httpx.get(url, timeout=2.0)
                if response.status_code < 500:
                    return
            except httpx.HTTPError as exc:
                last_error = str(exc)
            time.sleep(0.5)
        raise RuntimeError(f"{name} at {url} did not become ready: {last_error}")
