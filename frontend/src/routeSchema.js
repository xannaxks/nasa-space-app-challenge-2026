// Route request schema for POST /route (backend v2).
// Mirrors the backend's expected JSON exactly; empty fields are omitted
// so the backend falls back to its own optimal defaults.

export const DEFAULT_WEIGHTS = {
  w_elevation: 1,
  w_continuous_elevation: 0.5,
  w_roughness: 0.8,
  w_obstacles: 1,
  w_terrain_geology: 0.6,
  w_terrain_ir: 0.3,
  w_thermal: 0.3,
};

export const DEFAULT_ROUGHNESS = {
  method: 'detrended_rms',
  neighborhood_radius: 1,
  percentile_low: 10,
  percentile_high: 90,
  detrend: true,
  slope_threshold_deg: 15,
  tri_threshold_m: 4,
};

export const DEFAULT_OBSTACLES = {
  method: 'detrended_residual',
  neighborhood_radius: 1,
  detrend: true,
  residual_threshold_m: 3,
  slope_threshold_deg: 15,
  tri_threshold_m: 4,
  multi_thresholds_m: [0],
};

export const PENALTY_KEYS = [
  'asc_penalty',
  'desc_penalty',
  'flat_penalty',
  'continuous_asc_penalty',
  'continuous_desc_penalty',
  'continuous_flat_penalty',
  'terrain_roughness_penalty',
  'thermal_swing_risk_penalty',
  'obstacle_density_penalty',
  'terrain_type_ir_based_penalty',
];

export const DEFAULT_MISC = {
  terrain_source: 'ir_swing',
  elevation_direction_threshold: 1,
  geology_default_penalty: 0.5,
  max_expansions: '',
  return_path_cells: true,
  max_path_cells: 20000,
};

const isEmpty = (v) => v === '' || v == null;

/** Build the POST /route body from sidebar params + picked points. */
export function buildRoutePayload(points, params = {}) {
  const waypoints = points.map((p) => {
    if (p.pixel == null || !Number.isInteger(p.pixel.row) || !Number.isInteger(p.pixel.col)) {
      throw new Error(`"${p.name || 'Point'}" is off-grid — pick a point inside the map.`);
    }
    return { row: p.pixel.row, col: p.pixel.col };
  });

  const body = { waypoints };

  // --- weights (7 numbers; empty = omitted) ---
  const weights = {};
  for (const k of Object.keys(DEFAULT_WEIGHTS)) {
    const v = params[k];
    if (!isEmpty(v)) weights[k] = Number(v);
  }
  if (Object.keys(weights).length) body.weights = weights;

  // --- terrain source + elevation threshold ---
  if (!isEmpty(params.terrain_source)) body.terrain_source = params.terrain_source;
  if (!isEmpty(params.elevation_direction_threshold)) {
    body.elevation_direction_threshold = Number(params.elevation_direction_threshold);
  }

  // --- roughness block ---
  const roughness = {};
  for (const k of Object.keys(DEFAULT_ROUGHNESS)) {
    const v = params[`roughness_${k}`];
    if (k === 'multi_thresholds_m') continue; // obstacles-only
    if (!isEmpty(v)) {
      if (typeof DEFAULT_ROUGHNESS[k] === 'boolean') roughness[k] = v === true || v === 'true';
      else if (typeof DEFAULT_ROUGHNESS[k] === 'number') roughness[k] = Number(v);
      else roughness[k] = v;
    }
  }
  if (Object.keys(roughness).length) body.roughness = roughness;

  // --- obstacles block ---
  const obstacles = {};
  for (const k of Object.keys(DEFAULT_OBSTACLES)) {
    const v = params[`obstacles_${k}`];
    if (k === 'multi_thresholds_m') {
      if (!isEmpty(v)) {
        // accept "0, 5" or "[0,5]" or [0]
        if (Array.isArray(v)) obstacles[k] = v.map(Number);
        else if (typeof v === 'string') {
          const nums = v
            .replace(/[\[\]]/g, '')
            .split(',')
            .map((s) => s.trim())
            .filter((s) => s !== '')
            .map(Number);
          if (nums.length) obstacles[k] = nums;
        } else obstacles[k] = [Number(v)];
      }
      continue;
    }
    if (!isEmpty(v)) {
      if (typeof DEFAULT_OBSTACLES[k] === 'boolean') obstacles[k] = v === true || v === 'true';
      else if (typeof DEFAULT_OBSTACLES[k] === 'number') obstacles[k] = Number(v);
      else obstacles[k] = v;
    }
  }
  if (Object.keys(obstacles).length) body.obstacles = obstacles;

  // --- penalties (expression strings; empty = omitted) ---
  const penalties = {};
  for (const k of PENALTY_KEYS) {
    const v = params[`penalty_${k}`];
    if (!isEmpty(v)) penalties[k] = String(v);
  }
  if (Object.keys(penalties).length) body.penalties = penalties;

  // --- geology penalties ---
  const geoPen = {};
  if (!isEmpty(params.geology_penalties)) {
    try {
      Object.assign(geoPen, JSON.parse(params.geology_penalties));
    } catch {
      throw new Error('Geology penalties is not valid JSON');
    }
  }
  if (Object.keys(geoPen).length || !isEmpty(params.geology_default_penalty)) {
    body.geology = {};
    if (Object.keys(geoPen).length) body.geology.penalties = geoPen;
    if (!isEmpty(params.geology_default_penalty)) {
      body.geology.default_penalty = Number(params.geology_default_penalty);
    }
  }

  // --- limits ---
  if (!isEmpty(params.max_expansions)) body.max_expansions = Number(params.max_expansions);
  if (params.return_path_cells !== undefined && params.return_path_cells !== '') {
    body.return_path_cells = params.return_path_cells === true || params.return_path_cells === 'true';
  }
  if (!isEmpty(params.max_path_cells)) body.max_path_cells = Number(params.max_path_cells);

  // --- raw JSON override (merged last, wins) ---
  if (!isEmpty(params._custom)) {
    try {
      Object.assign(body, JSON.parse(params._custom));
    } catch {
      throw new Error('Custom JSON params are not valid JSON');
    }
  }

  return body;
}
