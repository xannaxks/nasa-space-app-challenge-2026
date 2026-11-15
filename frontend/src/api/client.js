// Thin wrapper around the FastAPI backend.
// Only route calculation uses the backend now; all map layers load from
// local static files (frontend/public/maps/) via src/map/localMaps.js.

import { API_BASE } from '../config.js';

export class ApiError extends Error {
  constructor(message, status, payload) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.payload = payload;
  }
}

async function request(path, options = {}) {
  const url = `${API_BASE}${path}`;
  const method = options.method || 'GET';
  let parsedBody;
  try {
    parsedBody = options.body ? JSON.parse(options.body) : undefined;
  } catch {
    parsedBody = options.body;
  }
  // Log every backend request before sending (method + url + parsed JSON body).
  console.log(`[api] ${method} ${url}`, parsedBody !== undefined ? parsedBody : '');
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  const text = await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }
  // Log the response (status + parsed body) for debugging.
  console.log(`[api] <- ${res.status} ${method} ${url}`, data);
  if (!res.ok) {
    throw new ApiError(
      (data && data.detail) || `Request failed: ${res.status}`,
      res.status,
      data,
    );
  }
  return data;
}

export const api = {
  get: (path) => request(path),

  post: (path, body) =>
    request(path, { method: 'POST', body: JSON.stringify(body ?? {}) }),

  // ---- map endpoints (legacy backend tile API, unused — kept for reference) ----
  // Layers now load from local static files; see src/map/localMaps.js.
  geologyVector: () => request('/maps/geology/vector.geojson'),
  geologyStats: () => request('/maps/geology/stats').catch(() => null),

  /**
   * Raster tile URL template for a layer, e.g. layer = 'dtm' | 'hillshade' | 'slope' | 'day' | 'night'.
   * Backend serves /maps/{layer}/tiles/{z}/{x}/{y}.png
   */
  tileUrl: (layer) => `${API_BASE}/maps/${layer}/tiles/{z}/{x}/{y}.png`,

  /** Pixel value + centre coords lookup: GET /maps/{layer}/pixel?row=&col= */
  pixelValue: (layer, row, col) =>
    request(`/maps/${layer}/pixel?row=${row}&col=${col}`),

  /** Route calculation (raster points). Vector points are translated backend-side. */
  calcRoute: (payload) => request('/route', { method: 'POST', body: JSON.stringify(payload) }),
};

export default api;
