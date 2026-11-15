# Frontend — React + Vite + MapLibre (MTM100m ready)

Scaffold that is ready to **fetch data from the backend and render it**.
Decoupled from backend internals: it only assumes the HTTP contract below.
Point `VITE_API_BASE` at FastAPI (default `http://localhost:8000`).

## Run

```powershell
cd frontend
npm install
npm run dev      # http://localhost:5173
npm run build    # production bundle -> dist/
```

Dev proxy forwards `/maps`, `/route`, `/routes` to `http://localhost:8000`
(see `vite.config.js`). For production set `VITE_API_BASE`.

## Expected backend contract (align when you wire it up)

| Method | URL | Purpose |
|---|---|---|
| `GET` | `/maps/geology/vector.geojson` | geology polygons (MTM metres or lng/lat — auto-detected) |
| `GET` | `/maps/{layer}/tiles/{z}/{x}/{y}.png` | raster XYZ tiles (`hillshade`, `dtm`, `slope`, `day`, `night`) |
| `GET` | `/maps/{layer}/pixel?row=&col=` | `{ value }` for click pixel inspect |
| `POST` | `/route` | `{ params, points: [{name, order, lng, lat, row, col}] }` → `{ path \| segments, waypoints, length_km, cost }` |

Missing endpoints are tolerated: tiles 404 = blank layer, vector falls back
to an offline placeholder, route calc falls back to a straight-line demo.

## Where layers are prepared

- `src/map/grid.js` — MTM100m grid (565×594, 100 m, origin from `alignment_stats.json`) + pixel↔MTM helpers.
- `src/map/projection.js` — MTM clon77_5E (Transverse Mercator, R=3396190) ↔ lng/lat via proj4; auto-detects metre GeoJSON.
- `src/map/layers.js` — **`MAP_LAYERS`: the layer registry.** Each entry knows how to FETCH (tile URL / GeoJSON) and RENDER (raster source vs styled vector fill+line) and INSPECT (click handler). Add a backend layer = append one object.
- `src/map/MapView.jsx` — owns the MapLibre instance; syncs `layerStates` (visibility/opacity/z-order) + route overlays; click → raster pixel / geology feature / route leg inspection; `picking` mode hides routes and forwards clicks as waypoints.
- `src/api/client.js` — `api` wrapper (`geologyVector`, `tileUrl`, `pixelValue`, `calcRoute`) + `ApiError`.
- `src/components/LayersPanel.jsx` — lower-left panel: rename, show/hide, opacity, reorder (rendered bottom = on top), default names Layer 1..N style via registry.
- `src/components/InspectCard.jsx` — click popup: pixel value + centre MTM coords, geology properties, route leg length/cost.
- `src/components/Sidebar.jsx` — right panel: cost-param form (defaults + custom JSON), waypoints (≤10, rename/reorder/remove, add-by-click), routes with per-route colour, line/points toggles, folded params.
- `src/App.jsx` — state + `POST /route`, dim overlay during calculation, invalid-param (HTTP 422) error screen, offline demo fallback.
- `src/config.js` — `API_BASE` + defaults. `public/loading.gif` — drop your loader here.

## Grid note

All rasters share the aligned 565×594 @100 m MTM grid, so one
`lngLat ↔ (row, col) ↔ MTM` conversion serves every layer — no per-layer
reprojection in the browser.
