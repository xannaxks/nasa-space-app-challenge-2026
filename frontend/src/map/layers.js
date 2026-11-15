// Layer descriptors for MapLibre — all LOCAL, zero backend calls.
// Rasters: pre-converted PNGs in public/maps/ as `image` sources.
// Vector: simplified GeoJSON in public/maps/ as `geojson` source.
//
// PNG value mappings (see scripts/convert_maps_to_png.py + localMaps.js):
//   norm01 : v = px / 255          (Day, Night, CTX mosaic)
//   slope40: v = px / 255 * 40 deg (slope)
//   raw    : v = px                (hillshade, display only)

import { fetchLocalGeology, inspectLocalPixel } from './localMaps.js';
import { GEOUNIT_LOOKUP } from './grid.js';

// Distinct palette for vector geology units (14 codes, see geounit_lookup.json).
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
 *   id, name, kind: 'raster' | 'vector',
 *   defaultVisible, defaultOpacity,
 *   file,               // raster PNG filename under public/maps/
 *   fetchGeojson?,      // () => Promise<GeoJSON> for the vector layer
 *   styleVector?,       // (map, sourceId) => void — adds fill/line layers
 *   inspect?,           // async (lngLat|feature, helpers) => {title, rows:[{k,v}]}
 * }
 */

function rasterInspect(title, unit) {
  return async (lngLat, helpers) => {
    const px = helpers?.lngLatToPixel?.(lngLat);
    if (!px) return null;
    const hit = await inspectLocalPixel(title, px).catch(() => null);
    const rows = hit
      ? [
          {
            k: `value${unit ? ` (${unit})` : ''}`,
            v: unit === 'deg' ? hit.value.toFixed(2) : hit.value.toFixed(4),
          },
          { k: 'png gray 0-255', v: String(hit.raw) },
          { k: 'centre (MTM m)', v: `x=${px.mtm.x.toFixed(1)}, y=${px.mtm.y.toFixed(1)}` },
          { k: 'lng/lat', v: `${lngLat.lng.toFixed(5)}, ${lngLat.lat.toFixed(5)}` },
        ]
      : [{ k: 'note', v: 'local PNG not loaded yet' }];
    return { title: `${title} pixel r=${px.row} c=${px.col}`, rows, lngLat };
  };
}

export const MAP_LAYERS = [
  {
    id: 'hillshade',
    name: 'Hillshade (DTM)',
    kind: 'raster',
    defaultVisible: true,
    defaultOpacity: 1,
    file: 'DTM_hillshade_MTM100m.png',
    inspect: rasterInspect('hillshade', null),
  },
  {
    id: 'dtm',
    name: 'DTM elevation (norm)',
    kind: 'raster',
    defaultVisible: false,
    defaultOpacity: 1,
    file: 'DTM_CTX_mosaic_MTM100m_norm01.png',
    inspect: rasterInspect('dtm', '0-1'),
  },
  {
    id: 'slope',
    name: 'Slope (deg)',
    kind: 'raster',
    defaultVisible: false,
    defaultOpacity: 0.85,
    file: 'DTM_slope_deg_MTM100m.png',
    inspect: rasterInspect('slope', 'deg'),
  },
  {
    id: 'day',
    name: 'THEMIS Day IR',
    kind: 'raster',
    defaultVisible: false,
    defaultOpacity: 1,
    file: 'THEMIS_Day_MTM100m_norm01.png',
    inspect: rasterInspect('day', '0-1'),
  },
  {
    id: 'night',
    name: 'THEMIS Night IR',
    kind: 'raster',
    defaultVisible: false,
    defaultOpacity: 1,
    file: 'THEMIS_Night_MTM100m_norm01.png',
    inspect: rasterInspect('night', '0-1'),
  },
  {
    id: 'geology',
    name: 'Geology units (vector)',
    kind: 'vector',
    defaultVisible: true,
    defaultOpacity: 0.55,
    fetchGeojson: () => fetchLocalGeology(),
    // colours each unit by its `_code` (1-14, see geounit_lookup.json)
    styleVector: (map, sourceId, opacity) => {
      const match = ['match', ['coalesce', ['get', '_code'], ['get', 'unit_id'], ['get', 'value']]];
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
      const p = { ...feature.properties };
      const code = Number(p._code ?? p.unit_id ?? p.value);
      if (Number.isFinite(code) && GEOUNIT_LOOKUP[code] && !p.symbol) p.symbol = GEOUNIT_LOOKUP[code];
      return {
        title: `Geology unit ${p.symbol ?? p.unit ?? p.name ?? code ?? ''}`,
        rows: Object.entries(p).map(([k, v]) => ({ k, v: String(v) })),
      };
    },
  },
];
