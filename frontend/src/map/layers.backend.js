// Ready-made layer descriptors for MapLibre.
// Each entry knows how to FETCH its data (via api/client.js) and how to RENDER
// itself (MapLibre source + layer spec). The map component consumes these
// generically — adding a new backend layer = appending one object here.

import { api } from '../api/client.js';

// Distinct palette for vector geology units.
const GEO_COLORS = [
  '#e41a1c', '#377eb8', '#4daf4a', '#984ea3', '#ff7f00', '#ffff33',
  '#a65628', '#f781bf', '#999999', '#66c2a5', '#fc8d62', '#8da0cb',
  '#e78ac3', '#a6d854',
];

export function geounitColor(id) {
  const n = Number(id);
  if (!Number.isFinite(n)) return '#cccccc';
  return GEO_COLORS[(n - 1) % GEO_COLORS.length];
}

/**
 * Layer spec:
 * {
 *   id, name, kind: 'raster' | 'vector' | 'route',
 *   defaultVisible, defaultOpacity,
 *   tileUrl?,           // raster XYZ template
 *   fetchGeojson?,      // () => Promise<GeoJSON> for vector layers
 *   styleVector?,       // (map, sourceId) => void — adds fill/line layers
 *   inspect?,           // async (lngLat | feature) => {title, rows:[{k,v}]} for click popup
 * }
 */
export const MAP_LAYERS = [
  {
    id: 'hillshade',
    name: 'Hillshade (DTM)',
    kind: 'raster',
    defaultVisible: true,
    defaultOpacity: 1,
    tileUrl: () => api.tileUrl('hillshade'),
    inspect: async () => null, // hillshade has no physical per-pixel value
  },
  {
    id: 'dtm',
    name: 'DTM elevation (norm)',
    kind: 'raster',
    defaultVisible: false,
    defaultOpacity: 1,
    tileUrl: () => api.tileUrl('dtm'),
    inspect: async (lngLat, helpers) => {
      const px = helpers?.lngLatToPixel?.(lngLat);
      if (!px) return null;
      const data = await api.pixelValue('dtm', px.row, px.col).catch(() => null);
      return {
        title: `DTM pixel r=${px.row} c=${px.col}`,
        rows: [
          { k: 'value', v: data?.value ?? '(backend offline)' },
          { k: 'centre (MTM m)', v: `x=${px.mtm.x.toFixed(1)}, y=${px.mtm.y.toFixed(1)}` },
          { k: 'lng/lat', v: `${lngLat.lng.toFixed(5)}, ${lngLat.lat.toFixed(5)}` },
        ],
      };
    },
  },
  {
    id: 'slope',
    name: 'Slope (deg)',
    kind: 'raster',
    defaultVisible: false,
    defaultOpacity: 0.85,
    tileUrl: () => api.tileUrl('slope'),
    inspect: async (lngLat, helpers) => {
      const px = helpers?.lngLatToPixel?.(lngLat);
      if (!px) return null;
      const data = await api.pixelValue('slope', px.row, px.col).catch(() => null);
      return {
        title: `Slope pixel r=${px.row} c=${px.col}`,
        rows: [
          { k: 'slope', v: data?.value ?? '(backend offline)' },
          { k: 'centre (MTM m)', v: `x=${px.mtm.x.toFixed(1)}, y=${px.mtm.y.toFixed(1)}` },
        ],
      };
    },
  },
  {
    id: 'day',
    name: 'THEMIS Day IR',
    kind: 'raster',
    defaultVisible: false,
    defaultOpacity: 1,
    tileUrl: () => api.tileUrl('day'),
    inspect: async (lngLat, helpers) => {
      const px = helpers?.lngLatToPixel?.(lngLat);
      if (!px) return null;
      const data = await api.pixelValue('day', px.row, px.col).catch(() => null);
      return {
        title: `Day IR pixel r=${px.row} c=${px.col}`,
        rows: [
          { k: 'value', v: data?.value ?? '(backend offline)' },
          { k: 'centre (MTM m)', v: `x=${px.mtm.x.toFixed(1)}, y=${px.mtm.y.toFixed(1)}` },
        ],
      };
    },
  },
  {
    id: 'night',
    name: 'THEMIS Night IR',
    kind: 'raster',
    defaultVisible: false,
    defaultOpacity: 1,
    tileUrl: () => api.tileUrl('night'),
    inspect: async (lngLat, helpers) => {
      const px = helpers?.lngLatToPixel?.(lngLat);
      if (!px) return null;
      const data = await api.pixelValue('night', px.row, px.col).catch(() => null);
      return {
        title: `Night IR pixel r=${px.row} c=${px.col}`,
        rows: [
          { k: 'value', v: data?.value ?? '(backend offline)' },
          { k: 'centre (MTM m)', v: `x=${px.mtm.x.toFixed(1)}, y=${px.mtm.y.toFixed(1)}` },
        ],
      };
    },
  },
  {
    id: 'geology',
    name: 'Geology units (vector)',
    kind: 'vector',
    defaultVisible: true,
    defaultOpacity: 0.55,
    fetchGeojson: () => api.geologyVector(),
    // colours each unit by its `unit_id` / `value` property
    styleVector: (map, sourceId, opacity) => {
      const match = ['match', ['coalesce', ['get', 'unit_id'], ['get', 'value'], ['get', 'UNIT']]];
      Object.keys(GEO_COLORS.reduce((a, _, i) => ({ ...a, [i + 1]: 1 }), {})).forEach(() => {});
      for (let i = 1; i <= 14; i++) match.push(i, geounitColor(i));
      match.push('#cccccc');
      if (!map.getLayer(`${sourceId}-fill`)) {
        map.addLayer({
          id: `${sourceId}-fill`,
          type: 'fill',
          source: sourceId,
          paint: { 'fill-color': match, 'fill-opacity': opacity },
        });
      }
      if (!map.getLayer(`${sourceId}-line`)) {
        map.addLayer({
          id: `${sourceId}-line`,
          type: 'line',
          source: sourceId,
          paint: { 'line-color': '#111', 'line-width': 0.6, 'line-opacity': 0.8 },
        });
      }
    },
    inspect: async (feature) => {
      if (!feature?.properties) return null;
      const p = feature.properties;
      return {
        title: `Geology unit ${p.unit ?? p.name ?? p.unit_id ?? p.value ?? ''}`,
        rows: Object.entries(p).map(([k, v]) => ({ k, v: String(v) })),
      };
    },
  },
];

// Fallback GeoJSON shown when backend is unreachable so the UI is usable offline.
export function offlineGeologyFallback() {
  return {
    type: 'FeatureCollection',
    features: [
      {
        type: 'Feature',
        properties: { unit_id: 5, unit: 'Njf', note: 'offline placeholder' },
        geometry: {
          type: 'Polygon',
          coordinates: [
            [
              [77.3, 17.6],
              [77.9, 17.6],
              [77.9, 18.0],
              [77.3, 18.0],
              [77.3, 17.6],
            ],
          ],
        },
      },
    ],
  };
}
