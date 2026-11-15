import { GRID, isValidPixel } from './grid.js';

// Local static maps (Option A): pre-converted PNGs + simplified GeoJSON in
// frontend/public/maps/ — served by Vite, zero backend calls.
// PNGs are plain LINEAR 8-bit grayscale; the value mapping inverts
// pixel -> value for click-inspect (see scripts/convert_maps_to_png.py).
//
//   norm01 : v = px / 255            (Day, Night, CTX mosaic)
//   slope40: v = px / 255 * 40 deg   (slope)
//   raw    : v = px                  (hillshade 0-181, display only)

const MANIFEST_URL = 'maps/layers.json';
const GEOJSON_URL = 'maps/GeoUnits_vector_MTM100m_simplified.geojson';

let pngCache = {}; // layerId -> { mapping, data: Uint8Array, w, h }
let manifestPromise = null;

async function loadManifest() {
  if (!manifestPromise) {
    manifestPromise = fetch(MANIFEST_URL).then((r) => {
      if (!r.ok) throw new Error(`layers manifest missing: ${r.status}`);
      return r.json();
    });
  }
  return manifestPromise;
}

export async function getLayerManifest(layerId) {
  const m = await loadManifest();
  return m.layers?.[layerId] ?? null;
}

export function getSlopeMaxDeg() {
  return loadManifest().then((m) => m.slope_max_deg ?? 40).catch(() => 40);
}

/** Fetch + decode the static PNG for a raster layer into raw gray bytes. */
export async function loadPngBytes(layerId) {
  if (pngCache[layerId]) return pngCache[layerId];
  const entry = await getLayerManifest(layerId);
  if (!entry || entry.kind !== 'raster') throw new Error(`no local raster for ${layerId}`);
  const url = `maps/${entry.file}`;
  const blob = await fetch(url).then((r) => {
    if (!r.ok) throw new Error(`${url}: ${r.status}`);
    return r.blob();
  });
  const bmp = await createImageBitmap(blob);
  const canvas = document.createElement('canvas');
  canvas.width = bmp.width;
  canvas.height = bmp.height;
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  ctx.drawImage(bmp, 0, 0);
  const { data } = ctx.getImageData(0, 0, bmp.width, bmp.height);
  const gray = new Uint8Array(bmp.width * bmp.height);
  for (let i = 0; i < gray.length; i++) gray[i] = data[i * 4]; // R channel (grayscale PNG)
  const rec = { mapping: entry.mapping, data: gray, w: bmp.width, h: bmp.height };
  pngCache[layerId] = rec;
  return rec;
}

/** PNG gray pixel -> physical value, mirroring scripts/convert_maps_to_png.py. */
export function pngPixelToValue(px, mapping, slopeMax = 40) {
  if (mapping === 'norm01') return px / 255;
  if (mapping === 'slope40') return (px / 255) * slopeMax;
  return px; // 'raw' (hillshade): display DN 0-181
}

/** Local click-inspect for a raster layer: value + pixel + MTM centre. No backend. */
export async function inspectLocalPixel(layerId, px) {
  const { data, w, h, mapping } = await loadPngBytes(layerId);
  const { row, col } = px;
  if (!isValidPixel(row, col) || col >= w || row >= h) return null;
  const raw = data[row * w + col];
  const slopeMax = mapping === 'slope40' ? await getSlopeMaxDeg() : 40;
  const value = pngPixelToValue(raw, mapping, slopeMax);
  return { raw, value, mapping };
}

/** Display scaling factor for slope PNG: compress 0-40deg into 0-255.
 *  Kept linear so value recovery is exact-ish (px/255*40). */
export const SLOPE_PNG_MAX = 40;

let geojsonPromise = null;

/** Fetch the simplified geology GeoJSON (MTM metres; caller reprojects). */
export function fetchLocalGeology() {
  if (!geojsonPromise) {
    geojsonPromise = fetch(GEOJSON_URL).then((r) => {
      if (!r.ok) throw new Error(`${GEOJSON_URL}: ${r.status}`);
      return r.json();
    });
  }
  return geojsonPromise;
}

export function clearLocalCache() {
  pngCache = {};
  geojsonPromise = null;
  manifestPromise = null;
}

export { GRID };
