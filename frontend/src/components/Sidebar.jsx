import { useState } from 'react';
import {
  DEFAULT_WEIGHTS,
  DEFAULT_ROUGHNESS,
  DEFAULT_OBSTACLES,
  PENALTY_KEYS,
  DEFAULT_MISC,
} from '../routeSchema.js';

// Right sidebar: route cost params + waypoint picking + route results.
const ROUTE_COLORS = ['#ff5252', '#40c4ff', '#69f0ae', '#ffd740', '#e040fb', '#ff6e40'];

export default function Sidebar({
  open,
  onToggle,
  params,
  setParams,
  points,
  setPoints,
  picking,
  setPicking,
  onCalculate,
  calculating,
  routes,
  setRoutes,
  error,
}) {
  const [expandedRoute, setExpandedRoute] = useState(null);

  const addPoint = () => {
    if (points.length >= 10) return;
    setPicking(true);
  };

  const movePoint = (idx, dir) => {
    const j = idx + dir;
    if (j < 0 || j >= points.length) return;
    setPoints((prev) => {
      const next = [...prev];
      const [p] = next.splice(idx, 1);
      next.splice(j, 0, p);
      return next;
    });
  };

  const set = (k) => (e) => {
    const v = e.target.type === 'checkbox' ? e.target.checked : e.target.value;
    setParams((p) => ({ ...p, [k]: v }));
  };
  const num = (k, def) => (
    <label key={k}>
      {k}
      <input
        type="number"
        step="any"
        placeholder={String(def)}
        value={params[k] ?? ''}
        onChange={(e) => setParams((p) => ({ ...p, [k]: e.target.value === '' ? '' : Number(e.target.value) }))}
      />
    </label>
  );

  return (
    <div className={`sidebar ${open ? '' : 'hidden'}`}>
      <div className="sidebar-head">
        <strong>Mission panel</strong>
        <button onClick={onToggle}>{open ? 'Hide »' : '« Show'}</button>
      </div>
      {open && (
        <div className="sidebar-body">
          <section>
            <h3>Weights</h3>
            <div className="params-grid">
              {Object.entries(DEFAULT_WEIGHTS).map(([k, def]) => num(k, def))}
            </div>
            <div className="small">
              Empty = backend default ({Object.entries(DEFAULT_WEIGHTS).map(([k, v]) => `${k}=${v}`).join(', ')}).
            </div>
          </section>

          <section>
            <h3>Terrain</h3>
            <div className="params-grid">
              <label>
                terrain_source
                <input
                  type="text"
                  placeholder={DEFAULT_MISC.terrain_source}
                  value={params.terrain_source ?? ''}
                  onChange={set('terrain_source')}
                />
              </label>
              {num('elevation_direction_threshold', DEFAULT_MISC.elevation_direction_threshold)}
            </div>
            <label>
              <span className="row"><input type="checkbox" style={{ width: 'auto' }} checked={params.return_path_cells ?? DEFAULT_MISC.return_path_cells} onChange={set('return_path_cells')} /> return_path_cells</span>
            </label>
            <div className="params-grid">
              {num('max_path_cells', DEFAULT_MISC.max_path_cells)}
              <label>
                max_expansions
                <input
                  type="number"
                  step="any"
                  placeholder="backend default"
                  value={params.max_expansions ?? ''}
                  onChange={(e) => setParams((p) => ({ ...p, max_expansions: e.target.value === '' ? '' : Number(e.target.value) }))}
                />
              </label>
            </div>
          </section>

          <section>
            <h3>Roughness</h3>
            <div className="params-grid">
              <label>
                roughness_method
                <input type="text" placeholder={DEFAULT_ROUGHNESS.method} value={params.roughness_method ?? ''} onChange={set('roughness_method')} />
              </label>
              {num('roughness_neighborhood_radius', DEFAULT_ROUGHNESS.neighborhood_radius)}
              {num('roughness_percentile_low', DEFAULT_ROUGHNESS.percentile_low)}
              {num('roughness_percentile_high', DEFAULT_ROUGHNESS.percentile_high)}
              {num('roughness_slope_threshold_deg', DEFAULT_ROUGHNESS.slope_threshold_deg)}
              {num('roughness_tri_threshold_m', DEFAULT_ROUGHNESS.tri_threshold_m)}
            </div>
            <label>
              <span className="row"><input type="checkbox" style={{ width: 'auto' }} checked={params.roughness_detrend ?? DEFAULT_ROUGHNESS.detrend} onChange={(e) => setParams((p) => ({ ...p, roughness_detrend: e.target.checked }))} /> roughness_detrend</span>
            </label>
          </section>

          <section>
            <h3>Obstacles</h3>
            <div className="params-grid">
              <label>
                obstacles_method
                <input type="text" placeholder={DEFAULT_OBSTACLES.method} value={params.obstacles_method ?? ''} onChange={set('obstacles_method')} />
              </label>
              {num('obstacles_neighborhood_radius', DEFAULT_OBSTACLES.neighborhood_radius)}
              {num('obstacles_residual_threshold_m', DEFAULT_OBSTACLES.residual_threshold_m)}
              {num('obstacles_slope_threshold_deg', DEFAULT_OBSTACLES.slope_threshold_deg)}
              {num('obstacles_tri_threshold_m', DEFAULT_OBSTACLES.tri_threshold_m)}
            </div>
            <label>
              obstacles_multi_thresholds_m (e.g. 0, 5)
              <input type="text" placeholder="[0]" value={params.obstacles_multi_thresholds_m ?? ''} onChange={set('obstacles_multi_thresholds_m')} />
            </label>
            <label>
              <span className="row"><input type="checkbox" style={{ width: 'auto' }} checked={params.obstacles_detrend ?? DEFAULT_OBSTACLES.detrend} onChange={(e) => setParams((p) => ({ ...p, obstacles_detrend: e.target.checked }))} /> obstacles_detrend</span>
            </label>
          </section>

          <section>
            <h3>Penalties (expressions)</h3>
            {PENALTY_KEYS.map((k) => (
              <label key={k}>
                {k}
                <input
                  type="text"
                  placeholder="backend default"
                  value={params[`penalty_${k}`] ?? ''}
                  onChange={set(`penalty_${k}`)}
                />
              </label>
            ))}
            <label>
              Geology penalties JSON (e.g. {'{"3": 1.2}'})
              <textarea
                rows={2}
                placeholder='{"3": 1.2}'
                value={params.geology_penalties ?? ''}
                onChange={set('geology_penalties')}
              />
            </label>
            <div className="params-grid">
              {num('geology_default_penalty', DEFAULT_MISC.geology_default_penalty)}
            </div>
          </section>

          <section>
            <h3>Raw JSON override</h3>
            <label>
              Merged over everything above
              <textarea
                rows={3}
                placeholder='{"weights": {"w_thermal": 2.0}}'
                value={params._custom ?? ''}
                onChange={set('_custom')}
              />
            </label>
          </section>

          <section>
            <h3>Waypoints ({points.length}/10)</h3>
            <div className="row">
              <button className="primary" onClick={addPoint} disabled={points.length >= 10 || picking}>
                {picking ? 'Click on map…' : '+ Add point'}
              </button>
              {picking && <button onClick={() => setPicking(false)}>Cancel</button>}
            </div>
            {points.map((p, i) => (
              <div className="point-row" key={p.id}>
                <input
                  type="text"
                  value={p.name}
                  onChange={(e) => setPoints((prev) => prev.map((q) => (q.id === p.id ? { ...q, name: e.target.value } : q)))}
                />
                <div className="small">
                  #{i + 1} · {p.lngLat ? `${p.lngLat.lng.toFixed(4)}, ${p.lngLat.lat.toFixed(4)}` : '?'}
                  {p.pixel ? ` · px r=${p.pixel.row} c=${p.pixel.col}` : ' · off-grid'}
                </div>
                <div className="row">
                  <button onClick={() => movePoint(i, -1)} title="earlier">◀</button>
                  <button onClick={() => movePoint(i, +1)} title="later">▶</button>
                  <button className="danger" onClick={() => setPoints((prev) => prev.filter((q) => q.id !== p.id))}>Remove</button>
                </div>
              </div>
            ))}
            <div className="row" style={{ marginTop: 8 }}>
              <button className="primary" onClick={onCalculate} disabled={calculating || points.length < 2}>
                {calculating ? 'Calculating…' : 'Calculate route'}
              </button>
            </div>
            {error && <div className="small" style={{ color: '#ff8a8a' }}>{error}</div>}
          </section>

          <section>
            <h3>Routes ({routes.length})</h3>
            {routes.map((r, ri) => (
              <div className="point-row" key={r.id}>
                <div className="route-legend">
                  <span className="dot" style={{ background: r.color || ROUTE_COLORS[ri % ROUTE_COLORS.length] }} />
                  <input
                    type="text"
                    value={r.name}
                    onChange={(e) => setRoutes((prev) => prev.map((q) => (q.id === r.id ? { ...q, name: e.target.value } : q)))}
                  />
                </div>
                <div className="small">
                  {r.summary?.length_km != null && <>length {Number(r.summary.length_km).toFixed(2)} km · </>}
                  {r.summary?.cost != null && <>cost {Number(r.summary.cost).toFixed(2)}</>}
                </div>
                <div className="row">
                  <label className="row small"><input type="checkbox" checked={r.visible !== false} onChange={(e) => setRoutes((prev) => prev.map((q) => (q.id === r.id ? { ...q, visible: e.target.checked } : q)))} /> route</label>
                  <label className="row small"><input type="checkbox" checked={r.showLine !== false} onChange={(e) => setRoutes((prev) => prev.map((q) => (q.id === r.id ? { ...q, showLine: e.target.checked } : q)))} /> line</label>
                  <label className="row small"><input type="checkbox" checked={r.showPoints !== false} onChange={(e) => setRoutes((prev) => prev.map((q) => (q.id === r.id ? { ...q, showPoints: e.target.checked } : q)))} /> points</label>
                  <button className="danger" onClick={() => setRoutes((prev) => prev.filter((q) => q.id !== r.id))}>✕</button>
                </div>
                <details open={expandedRoute === r.id} onToggle={(e) => setExpandedRoute(e.target.open ? r.id : null)}>
                  <summary className="small">params & segments</summary>
                  <pre className="small" style={{ whiteSpace: 'pre-wrap' }}>
                    {JSON.stringify({ params: r.params, summary: r.summary }, null, 2)}
                  </pre>
                </details>
              </div>
            ))}
            {!routes.length && <div className="small">No routes yet — pick ≥2 waypoints and calculate.</div>}
          </section>
        </div>
      )}
    </div>
  );
}

export { ROUTE_COLORS };
