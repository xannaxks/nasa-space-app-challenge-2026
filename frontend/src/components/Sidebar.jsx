import { useState } from 'react';

// Right sidebar: route cost params + waypoint picking + route results.
const DEFAULT_PARAMS = {
  w_slope: 1.0,
  w_roughness: 1.0,
  w_thermal: 0.5,
  w_geology: 0.3,
  max_slope_deg: 25,
};

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

  return (
    <div className={`sidebar ${open ? '' : 'hidden'}`}>
      <div className="sidebar-head">
        <strong>Mission panel</strong>
        <button onClick={onToggle}>{open ? 'Hide »' : '« Show'}</button>
      </div>
      {open && (
        <div className="sidebar-body">
          <section>
            <h3>Cost parameters</h3>
            <div className="params-grid">
              {Object.entries(DEFAULT_PARAMS).map(([k, defVal]) => (
                <label key={k}>
                  {k}
                  <input
                    type="number"
                    step="any"
                    placeholder={String(defVal)}
                    value={params[k] ?? ''}
                    onChange={(e) => setParams((p) => ({ ...p, [k]: e.target.value === '' ? '' : Number(e.target.value) }))}
                  />
                </label>
              ))}
            </div>
            <div className="small">Empty = backend default ({Object.entries(DEFAULT_PARAMS).map(([k, v]) => `${k}=${v}`).join(', ')}).</div>
            <label>
              Custom JSON params (merged over the above)
              <textarea
                rows={3}
                placeholder='{"w_slope": 2.0, "penalty": "a*2"}'
                value={params._custom ?? ''}
                onChange={(e) => setParams((p) => ({ ...p, _custom: e.target.value }))}
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
                    {JSON.stringify({ params: r.params, segments: r.summary?.segments }, null, 2)}
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
