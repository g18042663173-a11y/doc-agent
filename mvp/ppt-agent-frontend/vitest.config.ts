import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': new URL('./src', import.meta.url).pathname
    }
  },
  test: {
    environment: 'jsdom',
    globals: false,
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    setupFiles: ['./src/test/setup.ts'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'lcov'],
      include: ['src/**/*.{ts,tsx}'],
      exclude: ['src/main.tsx', 'src/router.tsx', 'src/vite-env.d.ts', 'src/test/**', 'src/**/*.test.{ts,tsx}'],
      thresholds: {
        statements: 70,
        branches: 70,
        functions: 70,
        lines: 70
      }
    }
  }
});
