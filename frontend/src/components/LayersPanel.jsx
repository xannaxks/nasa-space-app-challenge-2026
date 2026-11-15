import { MAP_LAYERS } from '../map/layers.js';

// Lower-left layer stack: fixed names, show/hide, opacity, reorder.
export default function LayersPanel({ layerStates, setLayerStates }) {
  const move = (id, dir) => {
    const sorted = [...layerStates].sort((a, b) => a.order - b.order);
    const i = sorted.findIndex((s) => s.id === id);
    const j = i + dir;
    if (i < 0 || j < 0 || j >= sorted.length) return;
    const a = sorted[i];
    const b = sorted[j];
    const orderOf = Object.fromEntries(sorted.map((s) => [s.id, s.order]));
    orderOf[a.id] = b.order;
    orderOf[b.id] = a.order;
    setLayerStates((prev) => prev.map((s) => ({ ...s, order: orderOf[s.id] ?? s.order })));
  };

  const patch = (id, p) =>
    setLayerStates((prev) => prev.map((s) => (s.id === id ? { ...s, ...p } : s)));

  const ordered = [...layerStates].sort((a, b) => b.order - a.order); // top first

  return (
    <div className="hud layers-panel">
      <h3>Layers</h3>
      {ordered.map((s) => {
        const def = MAP_LAYERS.find((l) => l.id === s.id);
        if (!def) return null;
        return (
          <div className="layer-row" key={s.id}>
            <input
              type="checkbox"
              checked={s.visible}
              onChange={(e) => patch(s.id, { visible: e.target.checked })}
              title="show / hide"
            />
            <span className="layer-name" title={def.name}>
              {def.name}
            </span>
            <input
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={s.opacity}
              onChange={(e) => patch(s.id, { opacity: Number(e.target.value) })}
              title="opacity"
              style={{ width: 60 }}
            />
            <button onClick={() => move(s.id, +1)} title="move up">▲</button>
            <button onClick={() => move(s.id, -1)} title="move down">▼</button>
          </div>
        );
      })}
      <div className="small">Top = rendered on top. Click map to inspect topmost raster pixel / geology unit.</div>
    </div>
  );
}
