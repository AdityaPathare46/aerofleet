// MapLibre GL v6 loader that pins the ESM worker URL via Vite's native worker bundler
// so GeoJSON overlays (airspace zones, mission polylines) work identically in vite dev,
// vite preview, and the packaged Tauri macOS/Windows desktop app (tauri://localhost).
import * as maplibregl from 'maplibre-gl'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'

maplibregl.setWorkerUrl(workerUrl)

export default maplibregl
export * from 'maplibre-gl'
