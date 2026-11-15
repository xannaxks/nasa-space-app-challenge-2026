import proj4 from 'proj4';
import { GRID, pixelToMtm, mtmToPixel } from './grid.js';

// MTM clon77_5E — Transverse Mercator on Mars 2000 sphere.
// WKT central_meridian = 77.5, lat origin 0, sphere R = 3396190 m.
const MTM_DEF =
  '+proj=tmerc +lat_0=0 +lon_0=77.5 +k=1 +x_0=0 +y_0=0 +a=3396190 +b=3396190 +units=m +no_defs';

proj4.defs('MTM', MTM_DEF);
proj4.defs('WGS84', '+proj=longlat +datum=WGS84 +no_defs');

export function mtmToLngLat(x, y) {
  const [lng, lat] = proj4('MTM', 'WGS84', [x, y]);
  return { lng, lat };
}

export function lngLatToMtm(lng, lat) {
  const [x, y] = proj4('WGS84', 'MTM', [lng, lat]);
  return { x, y };
}

/** row/col (raster pixel) -> { lng, lat } (MapLibre coords) */
export function pixelToLngLat(row, col) {
  const { x, y } = pixelToMtm(row, col);
  return mtmToLngLat(x, y);
}

/** MapLibre { lng, lat } -> { row, col, mtm } or null if outside grid */
export function lngLatToPixel(lng, lat) {
  const mtm = lngLatToMtm(lng, lat);
  const px = mtmToPixel(mtm.x, mtm.y);
  if (!px) return null;
  return { ...px, mtm };
}

export function getCenterLngLat() {
  return pixelToLngLat(GRID.height / 2, GRID.width / 2);
}

export function getBoundsLngLat() {
  const tl = pixelToLngLat(0, 0);
  const tr = pixelToLngLat(0, GRID.width - 1);
  const bl = pixelToLngLat(GRID.height - 1, 0);
  const br = pixelToLngLat(GRID.height - 1, GRID.width - 1);
  const lngs = [tl.lng, tr.lng, bl.lng, br.lng];
  const lats = [tl.lat, tr.lat, bl.lat, br.lat];
  return [
    [Math.min(...lngs), Math.min(...lats)],
    [Math.max(...lngs), Math.max(...lats)],
  ];
}

/**
 * Outer-corner quad of the full raster grid for MapLibre `image` sources.
 * Uses pixel EDGES (not centres) so PNGs overlay pixel-exact:
 *   TL = (originX, originY), BR = (originX + W*res, originY - H*res).
 * Returns [TL, TR, BR, BL] as [lng, lat] pairs (MapLibre image order).
 */
export function getImageCornersLngLat() {
  const x0 = GRID.originX;
  const y0 = GRID.originY;
  const x1 = GRID.originX + GRID.width * GRID.resM;
  const y1 = GRID.originY - GRID.height * GRID.resM;
  const tl = mtmToLngLat(x0, y0);
  const tr = mtmToLngLat(x1, y0);
  const br = mtmToLngLat(x1, y1);
  const bl = mtmToLngLat(x0, y1);
  return [
    [tl.lng, tl.lat],
    [tr.lng, tr.lat],
    [br.lng, br.lat],
    [bl.lng, bl.lat],
  ];
}

/**
 * Local GeoJSON may be in MTM metres (large coords) or Mars lon/lat.
 * Auto-detect: |x| > 1000 => metres, reproject every position to lng/lat.
 */
export function ensureLngLatGeojson(geojson) {
  if (!geojson || !geojson.features) return geojson;
  const sample = JSON.stringify(geojson).slice(0, 2000);
  const nums = [...sample.matchAll(/-?\d+\.\d+|-?\d+/g)].map((m) => Number(m[0]));
  const big = nums.some((n) => Math.abs(n) > 1000);
  if (!big) return geojson; // already lng/lat

  const convert = (coords) => {
    if (typeof coords[0] === 'number') {
      const { lng, lat } = mtmToLngLat(coords[0], coords[1]);
      return [lng, lat];
    }
    return coords.map(convert);
  };
  return {
    ...geojson,
    features: geojson.features.map((f) => ({
      ...f,
      geometry: f.geometry
        ? { ...f.geometry, coordinates: convert(f.geometry.coordinates) }
        : f.geometry,
    })),
  };
}
