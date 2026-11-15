// Click-inspection popup (raster pixel values, geology metadata, route info).
export default function InspectCard({ info, onClose }) {
  if (!info) return null;
  return (
    <div className="hud inspect-card">
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <strong style={{ fontSize: 13 }}>{info.title || 'Inspect'}</strong>
        <button onClick={onClose}>✕</button>
      </div>
      <table>
        <tbody>
          {(info.rows || []).map((r, i) => (
            <tr key={i}>
              <td>{r.k}</td>
              <td>{r.v}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {info.lngLat && (
        <div className="small">
          {Number(info.lngLat.lng).toFixed(5)}, {Number(info.lngLat.lat).toFixed(5)}
        </div>
      )}
    </div>
  );
}
