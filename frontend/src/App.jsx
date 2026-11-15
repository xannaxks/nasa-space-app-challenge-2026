import { useMemo, useState } from 'react';
import MapView from './map/MapView.jsx';
import LayersPanel from './components/LayersPanel.jsx';
import InspectCard from './components/InspectCard.jsx';
import Sidebar, { ROUTE_COLORS } from './components/Sidebar.jsx';
import { MAP_LAYERS } from './map/layers.js';
import { api, ApiError } from './api/client.js';
import { buildRoutePayload } from './routeSchema.js';
import { mtmToLngLat } from './map/projection.js';
import { GRID } from './map/grid.js';

let uid = 1;
const nid = (p) => `${p}-${uid++}`;

export default function App() {
  const [layerStates, setLayerStates] = useState(() =>
    MAP_LAYERS.map((l, i) => ({
      id: l.id,
      name: l.name,
      visible: l.defaultVisible,
      opacity: l.defaultOpacity ?? 1,
      order: i,
    })),
  );
  const [inspect, setInspect] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [params, setParams] = useState({});
  const [points, setPoints] = useState([]);
  const [picking, setPicking] = useState(false);
  const [calculating, setCalculating] = useState(false);
  const [routes, setRoutes] = useState([]);
  const [error, setError] = useState('');
  const [fatal, setFatal] = useState('');

  const mapRoutes = useMemo(
    () =>
      routes.map((r, i) => ({
        id: r.id,
        color: r.color || ROUTE_COLORS[i % ROUTE_COLORS.length],
        visible: r.visible !== false,
        showLine: r.showLine !== false,
        showPoints: r.showPoints !== false,
        geojson: r.geojson,
      })),
    [routes],
  );

  const handlePick = (lngLat, pixel) => {
    if (points.length >= 10) {
      setPicking(false);
      return;
    }
    setPoints((prev) => [
      ...prev,
      {
        id: nid('pt'),
        name: `Point ${prev.length + 1}`,
        lngLat,
        pixel: pixel ? { row: pixel.row, col: pixel.col, x: pixel.mtm.x, y: pixel.mtm.y } : null,
      },
    ]);
    setPicking(false);
  };

  const buildPayload = () => buildRoutePayload(points, params);

  // Convert backend route response -> GeoJSON line + points.
  // Backend v2 returns { path: [{row,col}...] (+ optional lng/lat cases below) }.
  const toGeojson = (resp, color) => {
    const lineFeatures = [];
    const pointFeatures = [];
    const segs = resp.segments || resp.legs || [];
    if (Array.isArray(segs) && segs.length) {
      segs.forEach((s, i) => {
        const coords = normalizeCoords(s.path || s.coords || s.line || []);
        if (coords.length) {
          lineFeatures.push({
            type: 'Feature',
            properties: {
              title: `Leg ${i + 1}: ${s.from || points[i]?.name || i + 1} → ${s.to || points[i + 1]?.name || i + 2}`,
              length_km: s.length_km ?? s.length ?? '',
              cost: s.cost ?? '',
            },
            geometry: { type: 'LineString', coordinates: coords },
          });
        }
      });
    } else {
      const coords = normalizeCoords(resp.path || resp.coords || []);
      if (coords.length) {
        lineFeatures.push({
          type: 'Feature',
          properties: { title: 'Route', length_km: resp.length_km ?? '', cost: resp.cost ?? '' },
          geometry: { type: 'LineString', coordinates: coords },
        });
      }
    }
    const wps = resp.waypoints || points.map((p, i) => ({ name: p.name, order: i + 1, lng: p.lngLat?.lng, lat: p.lngLat?.lat }));
    wps.forEach((w, i) => {
      if (w.lng != null && w.lat != null) {
        pointFeatures.push({
          type: 'Feature',
          properties: { title: `${w.name || `Point ${i + 1}`} (#${w.order ?? i + 1})`, order: w.order ?? i + 1, name: w.name || `Point ${i + 1}` },
          geometry: { type: 'Point', coordinates: [w.lng, w.lat] },
        });
      }
    });
    return {
      line: { type: 'FeatureCollection', features: lineFeatures },
      points: { type: 'FeatureCollection', features: pointFeatures },
    };
  };

  const handleCalculate = async () => {
    setError('');
    setFatal('');
    let payload;
    try {
      payload = buildPayload();
    } catch (e) {
      setError(e.message);
      return;
    }
    if (payload.waypoints.length < 2) {
      setError('Pick at least 2 waypoints.');
      return;
    }
    setCalculating(true);
    try {
      const resp = await api.calcRoute(payload);
      const idx = routes.length;
      const color = ROUTE_COLORS[idx % ROUTE_COLORS.length];
      setRoutes((prev) => [
        ...prev,
        {
          id: nid('route'),
          name: `Route ${prev.length + 1}`,
          color,
          visible: true,
          showLine: true,
          showPoints: true,
          params: payload,
          summary: { length_km: resp.length_km ?? resp.length, cost: resp.cost, segments: resp.segments ?? resp.legs },
          geojson: toGeojson(resp, color),
          raw: resp,
        },
      ]);
    } catch (e) {
      if (e instanceof ApiError && e.status === 422) {
        setFatal(typeof e.payload === 'string' ? e.payload : JSON.stringify(e.payload));
      } else {
        // Offline demo route: straight lines between waypoints so UI stays testable.
        const coords = points.map((p) => [p.lngLat.lng, p.lngLat.lat]);
        const idx = routes.length;
        const color = ROUTE_COLORS[idx % ROUTE_COLORS.length];
        setRoutes((prev) => [
          ...prev,
          {
            id: nid('route'),
            name: `Route ${prev.length + 1} (offline demo)`,
            color,
            visible: true,
            showLine: true,
            showPoints: true,
            params: payload,
            summary: { length_km: null, cost: null, segments: null },
            geojson: toGeojson({ path: coords }, color),
            raw: null,
          },
        ]);
        setError(`Backend unreachable (${e.message}) — drew straight-line demo.`);
      }
    } finally {
      setCalculating(false);
    }
  };

  return (
    <div className="app">
      <div className="map-wrap">
        <MapView
          layerStates={layerStates}
          routes={mapRoutes}
          picking={picking}
          onInspect={setInspect}
          onPick={handlePick}
        />
        <LayersPanel layerStates={layerStates} setLayerStates={setLayerStates} />
        <InspectCard info={inspect} onClose={() => setInspect(null)} />
        {picking && <div className="hud pick-banner">Click on the topmost map layer to place a point…</div>}
        {calculating && (
          <div className="dim">
            <h2>Doing complex route cost calculations… Please wait… </h2>
            <img src="https://i.pinimg.com/originals/94/d4/59/94d4590d97a6a882cf33f9e1e4fe513d.png?nii=t" alt="loading" onError={(e) => (e.target.style.display = 'none')} />
            <div className="small">It might take up to few minutes… (blame CPython) </div>
          </div>
        )}
        {fatal && (
          <div className="dim">
            <h2>Invalid parameters</h2>
            <pre style={{ maxWidth: 520, whiteSpace: 'pre-wrap' }}>{fatal}</pre>
            <button className="primary" onClick={() => setFatal('')}>Dismiss</button>
          </div>
        )}
      </div>
      {!sidebarOpen && (
        <button className="panel-reopen" onClick={() => setSidebarOpen(true)}>
          « Panel
        </button>
      )}
      <Sidebar
        open={sidebarOpen}
        onToggle={() => setSidebarOpen((v) => !v)}
        params={params}
        setParams={setParams}
        points={points}
        setPoints={setPoints}
        picking={picking}
        setPicking={setPicking}
        onCalculate={handleCalculate}
        calculating={calculating}
        routes={routes}
        setRoutes={setRoutes}
        error={error}
      />
    </div>
  );
}

function normalizeCoords(path) {
  if (!Array.isArray(path)) return [];
  // Backend v2: path = [{row, col}] raster cells (+ optionally lng/lat or x/y MTM metres).
  return path
    .map((p) => {
      if (Array.isArray(p) && p.length >= 2) {
        const [a, b] = p.map(Number);
        // [row, col] ints inside grid => raster cell; else assume [lng, lat].
        if (Number.isInteger(a) && Number.isInteger(b) && isGridCell(a, b)) {
          const { lng, lat } = mtmToLngLat(...Object.values(pixelToMtmApprox(a, b)));
          return [lng, lat];
        }
        return [a, b];
      }
      if (p && typeof p === 'object') {
        if (p.lng != null && p.lat != null) return [Number(p.lng), Number(p.lat)];
        if (p.lon != null && p.lat != null) return [Number(p.lon), Number(p.lat)];
        if (Number.isInteger(p.row) && Number.isInteger(p.col)) {
          const { lng, lat } = mtmToLngLat(...Object.values(pixelToMtmApprox(p.row, p.col)));
          return [lng, lat];
        }
        if (p.x != null && p.y != null) {
          const { lng, lat } = mtmToLngLat(Number(p.x), Number(p.y));
          return [lng, lat];
        }
      }
      return null;
    })
    .filter(Boolean);
}

// Local grid import without a hard dependency cycle (GRID math only).

function pixelToMtmApprox(row, col) {
  return { x: GRID.originX + (col + 0.5) * GRID.resM, y: GRID.originY - (row + 0.5) * GRID.resM };
}

function isGridCell(row, col) {
  return row >= 0 && row < GRID.height && col >= 0 && col < GRID.width;
}
