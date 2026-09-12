import { defineConfig, devices } from '@playwright/test';

const frontendPort = Number(process.env.E2E_FRONTEND_PORT || 3100);
const backendPort = Number(process.env.E2E_BACKEND_PORT || 8100);
const frontendUrl = `http://127.0.0.1:${frontendPort}`;
const backendUrl = `http://127.0.0.1:${backendPort}`;
const runId = process.env.E2E_RUN_ID || Date.now().toString();
const e2eRoot = `.e2e-data/${runId}`;

export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  expect: {
    timeout: 15_000
  },
  fullyParallel: false,
  workers: 1,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: frontendUrl,
    acceptDownloads: true,
    trace: 'retain-on-failure',
    viewport: { width: 1440, height: 900 }
  },
  webServer: [
    {
      command: [
        'cd .. &&',
        `DATA_DIR=${e2eRoot}/data`,
        `OUTPUT_DIR=${e2eRoot}/outputs`,
        `LOG_DIR=${e2eRoot}/logs`,
        'LLM_PROVIDER=mock',
        'PPT_RENDERER=python_pptx',
        `CORS_ORIGINS=${frontendUrl}`,
        `.venv/bin/python -m uvicorn app.api:app --host 127.0.0.1 --port ${backendPort}`
      ].join(' '),
      url: `${backendUrl}/health`,
      reuseExistingServer: false,
      timeout: 120_000
    },
    {
      command: `VITE_API_BASE_URL=${backendUrl}/api npm run dev -- --host 127.0.0.1 --port ${frontendPort}`,
      url: frontendUrl,
      reuseExistingServer: false,
      timeout: 120_000
    }
  ],
  projects: [
    {
      name: 'chrome',
      use: {
        ...devices['Desktop Chrome'],
        channel: 'chrome'
      }
    }
  ]
});
