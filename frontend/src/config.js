export const API_BASE =
  import.meta.env?.VITE_API_BASE || 'http://localhost:8000';

// MTM100m grid is defined in `src/map/grid.js` — single source of truth.
export const DEFAULT_MAP_CENTER = [77.62, 17.8];
export const DEFAULT_ZOOM = 8;
