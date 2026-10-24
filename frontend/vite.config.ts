/// <reference types="vitest" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath } from 'node:url';

const shared = fileURLToPath(new URL('../shared', import.meta.url));

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { '@shared': shared } },
  server: {
    port: 5173,
    fs: { allow: ['..'] },
    // Same-origin API in dev so auth cookies are first-party.
    // xfwd: send X-Forwarded-For so the backend rate-limits per visitor, not per proxy.
    proxy: { '/api': { target: process.env.VITE_API_PROXY ?? 'http://localhost:8000', changeOrigin: false, xfwd: true } },
  },
  test: { environment: 'jsdom', globals: true, setupFiles: ['./src/test-setup.ts'] },
});
