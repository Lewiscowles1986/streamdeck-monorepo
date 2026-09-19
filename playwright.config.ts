// Playwright configuration for the two E2E suites:
//  - project "demo-ui":      static demo build (no backend at all)
//  - project "full-stack":   API server on :8000 (dummy transport) + UI build
import { defineConfig, devices } from "@playwright/test";


const ROOT = __dirname;
const PORT_UI = 8080; // demo build (no backend)
const PORT_FULLSTACK_UI = 8081; // normal build talking to the dummy API
const PORT_API = 8000;

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: [["list"]],
  use: {
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "demo-ui",
      testMatch: /demo-ui\.spec\.ts/,
      use: { ...devices["Desktop Chrome"], baseURL: `http://localhost:${PORT_UI}` },
    },
    {
      name: "full-stack",
      testMatch: /full-stack\.spec\.ts/,
      use: {
        ...devices["Desktop Chrome"],
        baseURL: `http://localhost:${PORT_FULLSTACK_UI}`,
      },
    },
    {
      // Parity regression specs (agents UI, exit action, labels) — demo mock
      name: "parity-demo",
      testMatch: /parity-demo\.spec\.ts/,
      use: { ...devices["Desktop Chrome"], baseURL: `http://localhost:${PORT_UI}` },
    },
    {
      // Parity regression specs against the real API (dialect, dangling refs)
      name: "parity-fullstack",
      testMatch: /parity-fullstack\.spec\.ts/,
      use: {
        ...devices["Desktop Chrome"],
        baseURL: `http://localhost:${PORT_FULLSTACK_UI}`,
      },
    },
  ],
  webServer: [
    {
      // Demo build served statically (uvx . streamdeck demo) — no backend at all
      command: `${ROOT}/.venv/bin/python -m streamdeck.cli demo --port ${PORT_UI}`,
      url: `http://localhost:${PORT_UI}/`,
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
    },
    {
      // Normal build (uvx . streamdeck ui) talking to the dummy-transport API
      command: `${ROOT}/.venv/bin/python -m streamdeck.cli ui --port ${PORT_FULLSTACK_UI}`,
      url: `http://localhost:${PORT_FULLSTACK_UI}/`,
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
    },
    {
      // API with dummy transport (emulated deck) for the full-stack project
      command: `${ROOT}/.venv/bin/python -c "import os; os.environ['STREAMDECK_TRANSPORT']='dummy'; import uvicorn; from streamdeck.db import init_db; init_db(); uvicorn.run('streamdeck.app:app', host='127.0.0.1', port=${PORT_API})"`,
      url: `http://localhost:${PORT_API}/devices`,
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
    },
  ],
});