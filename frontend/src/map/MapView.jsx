import { useEffect, useRef } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { MAP_LAYERS } from './layers.js';
import { ensureLngLatGeojson, getCenterLngLat, getImageCornersLngLat, lngLatToPixel } from './projection.js';

// MapView owns the MapLibre instance.
// layerStates: [{ id, visible, opacity, order }]
// routes: [{ id, color, visible, showLine, showPoints, geojson: { line, points } }]
export default function MapView({ layerStates, routes, picking, onInspect, onPick }) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const stateRef = useRef({ layerStates, routes, picking });
  stateRef.current = { layerStates, routes, picking };
  const cbRef = useRef({ onInspect, onPick });
  cbRef.current = { onInspect, onPick };

  useEffect(() => {
    const center = getCenterLngLat();
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: {
        version: 8,
        sources: {},
        layers: [{ id: 'background', type: 'background', paint: { 'background-color': '#0b0e13' } }],
      },
      center: [center.lng, center.lat],
      zoom: 8,
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
    map.addControl(new maplibregl.ScaleControl({}), 'bottom-right');
    mapRef.current = map;

    map.on('load', () => {
      syncAll(map, stateRef.current);
      map.resize();
    });

    map.on('click', async (e) => {
      const st = stateRef.current;
      const px = lngLatToPixel(e.lngLat.lng, e.lngLat.lat);
      if (st.picking) {
        cbRef.current.onPick?.({ lng: e.lngLat.lng, lat: e.lngLat.lat }, px);
        return;
      }
      const routeIds = st.routes
        .flatMap((r) => [`route-line-${r.id}`, `route-pts-${r.id}`])
        .filter((id) => map.getLayer(id));
      if (routeIds.length) {
        const rf = map.queryRenderedFeatures(e.point, { layers: routeIds });
        if (rf.length) {
          const p = rf[0].properties || {};
          cbRef.current.onInspect?.({
            title: p.title || 'Route feature',
            rows: Object.entries(p)
              .filter(([k]) => k !== 'title')
              .map(([k, v]) => ({ k, v: String(v) })),
            lngLat: e.lngLat,
          });
          return;
        }
      }
      if (map.getLayer('src-geology-fill')) {
        try {
          const feats = map.queryRenderedFeatures(e.point, { layers: ['src-geology-fill'] });
          if (feats.length) {
            const def = MAP_LAYERS.find((l) => l.id === 'geology');
            const info = await def.inspect(feats[0]);
            cbRef.current.onInspect?.(info ? { ...info, lngLat: e.lngLat } : null);
            return;
          }
        } catch {
          // ignore
        }
      }
      const ordered = [...st.layerStates].sort((a, b) => a.order - b.order);
      const top = [...ordered].reverse().find((s) => {
        const def = MAP_LAYERS.find((l) => l.id === s.id);
        return s.visible && def && def.kind === 'raster' && def.inspect;
      });
      if (top && px) {
        const def = MAP_LAYERS.find((l) => l.id === top.id);
        try {
          const info = await def.inspect(e.lngLat, { lngLatToPixel });
          cbRef.current.onInspect?.(info ? { ...info, lngLat: e.lngLat } : null);
        } catch {
          cbRef.current.onInspect?.({
            title: `Pixel r=${px.row} c=${px.col}`,
            rows: [
              { k: 'centre (MTM m)', v: `x=${px.mtm.x.toFixed(1)}, y=${px.mtm.y.toFixed(1)}` },
              { k: 'note', v: 'local PNG not loaded yet' },
            ],
            lngLat: e.lngLat,
          });
        }
        return;
      }
      cbRef.current.onInspect?.(null);
    });

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (map.isStyleLoaded()) syncAll(map, { layerStates, routes, picking });
    else map.once('load', () => syncAll(map, { layerStates, routes, picking }));
  }, [layerStates, routes, picking]);

  return <div ref={containerRef} className="map-container" />;
}

function syncAll(map, { layerStates, routes, picking }) {
  syncBaseLayers(map, layerStates);
  syncRoutes(map, routes, picking);
}

function syncBaseLayers(map, layerStates) {
  const ordered = [...layerStates].sort((a, b) => a.order - b.order);
  for (const s of ordered) {
    const def = MAP_LAYERS.find((l) => l.id === s.id);
    if (!def) continue;
    const sourceId = `src-${s.id}`;
    try {
      if (def.kind === 'raster') {
        // Local PNG overlay: static `image` source anchored to the grid corners.
        if (!map.getSource(sourceId)) {
          map.addSource(sourceId, {
            type: 'image',
            url: `maps/${def.file}`,
            coordinates: getImageCornersLngLat(),
          });
          map.addLayer({ id: `lyr-${s.id}`, type: 'raster', source: sourceId });
        }
        map.setLayoutProperty(`lyr-${s.id}`, 'visibility', s.visible ? 'visible' : 'none');
        map.setPaintProperty(`lyr-${s.id}`, 'raster-opacity', s.opacity);
      } else if (def.kind === 'vector') {
        if (!map.getSource(sourceId)) {
          map.addSource(sourceId, { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
          if (def.styleVector) def.styleVector(map, sourceId, s.opacity);
          Promise.resolve()
            .then(() => def.fetchGeojson())
            .then((gj) => {
              const src = map.getSource(sourceId);
              if (src) src.setData(ensureLngLatGeojson(gj));
            })
            .catch(() => {
              // leave the empty collection; LayersPanel tooltip explains
            });
        }
        for (const lid of [`${sourceId}-fill`, `${sourceId}-line`]) {
          if (map.getLayer(lid)) {
            map.setLayoutProperty(lid, 'visibility', s.visible ? 'visible' : 'none');
            if (lid.endsWith('-fill')) map.setPaintProperty(lid, 'fill-opacity', s.opacity);
          }
        }
      }
    } catch {
      // ignore transient style errors
    }
  }
  try {
    for (const s of ordered) {
      const def = MAP_LAYERS.find((l) => l.id === s.id);
      if (!def) continue;
      if (def.kind === 'raster' && map.getLayer(`lyr-${s.id}`)) map.moveLayer(`lyr-${s.id}`);
      else {
        if (map.getLayer(`src-${s.id}-fill`)) map.moveLayer(`src-${s.id}-fill`);
        if (map.getLayer(`src-${s.id}-line`)) map.moveLayer(`src-${s.id}-line`);
      }
    }
    for (const lid of allRouteLayerIds(map)) map.moveLayer(lid);
  } catch {
    // noop
  }
}

function allRouteLayerIds(map) {
  const style = map.getStyle();
  const layers = (style && style.layers) || [];
  return layers.map((l) => l.id).filter((id) => id.startsWith('route-line-') || id.startsWith('route-pts-'));
}

function syncRoutes(map, routes, picking) {
  const visible = !picking;
  for (const r of routes) {
    const lineId = `route-line-${r.id}`;
    const ptsId = `route-pts-${r.id}`;
    const lineData = ensureLngLatGeojson(r.geojson && r.geojson.line) || { type: 'FeatureCollection', features: [] };
    const ptsData = ensureLngLatGeojson(r.geojson && r.geojson.points) || { type: 'FeatureCollection', features: [] };
    if (!map.getSource(lineId)) {
      map.addSource(lineId, { type: 'geojson', data: lineData });
      map.addLayer({ id: lineId, type: 'line', source: lineId, paint: { 'line-color': r.color, 'line-width': 3 } });
    } else {
      map.getSource(lineId).setData(lineData);
    }
    if (!map.getSource(ptsId)) {
      map.addSource(ptsId, { type: 'geojson', data: ptsData });
      map.addLayer({
        id: ptsId,
        type: 'circle',
        source: ptsId,
        paint: {
          'circle-radius': 6,
          'circle-color': '#fff',
          'circle-stroke-color': r.color,
          'circle-stroke-width': 3,
        },
      });
    } else {
      map.getSource(ptsId).setData(ptsData);
    }
    if (map.getLayer(lineId)) {
      map.setLayoutProperty(lineId, 'visibility', visible && r.visible && r.showLine !== false ? 'visible' : 'none');
    }
    if (map.getLayer(ptsId)) {
      map.setLayoutProperty(ptsId, 'visibility', visible && r.visible && r.showPoints !== false ? 'visible' : 'none');
    }
  }
  const want = new Set(routes.flatMap((r) => [`route-line-${r.id}`, `route-pts-${r.id}`]));
  for (const lid of allRouteLayerIds(map)) {
    if (!want.has(lid)) {
      try {
        if (map.getLayer(lid)) map.removeLayer(lid);
        if (map.getSource(lid)) map.removeSource(lid);
      } catch {
        // noop
      }
    }
  }
}
