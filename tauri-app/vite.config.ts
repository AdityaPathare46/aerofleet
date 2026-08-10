import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Tauri expects a fixed port in dev mode
const host = process.env.TAURI_DEV_HOST

export default defineConfig({
  plugins: [react()],
  clearScreen: false,
  server: {
    port: 1420,
    strictPort: true,
    host: host || false,
    hmr: host ? { protocol: 'ws', host, port: 1421 } : undefined,
    watch: {
      // Watch for Tauri config changes
      ignored: ['**/src-tauri/**'],
    },
  },
  envPrefix: ['VITE_', 'TAURI_ENV_*'],
  optimizeDeps: {
    // maplibre-gl ships its own web worker as a separate ESM chunk that
    // Vite's dependency pre-bundler doesn't resolve correctly — excluding
    // it avoids a dev-server crash (`maplibre-gl-worker.mjs` not found).
    exclude: ['maplibre-gl'],
  },
  worker: {
    format: 'es',
  },
  build: {
    // safari13 (Tauri's original template default) predates BigInt literal
    // syntax support in esbuild's compat table (Safari 14+) — maplibre-gl
    // v6's bundle uses BigInt literals, so a safari13 target production
    // build fails outright (`npm run dev` never caught this: Vite's dev
    // server doesn't apply this target transform, only `npm run build` does).
    target: process.env.TAURI_ENV_PLATFORM === 'windows' ? 'chrome105' : 'safari14',
    minify: !process.env.TAURI_ENV_DEBUG ? 'esbuild' : false,
    sourcemap: !!process.env.TAURI_ENV_DEBUG,
  },
})
