#!/usr/bin/env python3
"""One-time conversion: aligned/*.tif -> frontend/public/maps/*.png (Option A).

Run from repo root:  .venv/Scripts/python.exe scripts/convert_maps_to_png.py

All 5 rasters share the identical 565x594 MTM100m grid, so every PNG stays
pixel-aligned. PNGs are plain 8-bit LINEAR grayscale so the frontend can
invert pixel -> value for click-inspect without any backend:

  norm01 layers (Day, Night, CTX mosaic): px = round(v * 255)  ->  v = px/255
  hillshade (already uint8 0-181):        px = raw             ->  v = px
  slope (float32 0..36.59 deg):           px = round(v/40*255) ->  v = px/255*40

The vector map is NOT converted: the simplified GeoJSON
(GeoUnits_vector_MTM100m_simplified.geojson, 3.3 MB, same 1304 features)
is copied as-is.

Outputs in frontend/public/maps/ (served as-is by Vite, no backend):
  THEMIS_Day_MTM100m_norm01.png
  THEMIS_Night_MTM100m_norm01.png
  DTM_CTX_mosaic_MTM100m_norm01.png
  DTM_slope_deg_MTM100m.png
  DTM_hillshade_MTM100m.png
  GeoUnits_vector_MTM100m_simplified.geojson
  layers.json  (value-mapping manifest for the frontend)
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "aligned"
DST = ROOT / "frontend" / "public" / "maps"

SLOPE_MAX_DEG = 40.0  # fixed display scale; max data value is ~36.59 deg

# id, source tif, output png, mapping used
RASTERS = [
    ("day", "THEMIS_Day_MTM100m_norm01.tif", "THEMIS_Day_MTM100m_norm01.png", "norm01"),
    ("night", "THEMIS_Night_MTM100m_norm01.tif", "THEMIS_Night_MTM100m_norm01.png", "norm01"),
    ("dtm", "DTM_CTX_mosaic_MTM100m_norm01.tif", "DTM_CTX_mosaic_MTM100m_norm01.png", "norm01"),
    ("slope", "DTM_slope_deg_MTM100m.tif", "DTM_slope_deg_MTM100m.png", "slope40"),
    ("hillshade", "DTM_hillshade_MTM100m.tif", "DTM_hillshade_MTM100m.png", "raw"),
]

VECTOR = "GeoUnits_vector_MTM100m_simplified.geojson"


def to_png(arr: np.ndarray, mapping: str) -> Image.Image:
    a = np.asarray(arr, dtype=np.float64)
    if mapping == "norm01":
        px = np.round(np.clip(a, 0.0, 1.0) * 255.0)
    elif mapping == "slope40":
        px = np.round(np.clip(a, 0.0, SLOPE_MAX_DEG) / SLOPE_MAX_DEG * 255.0)
    elif mapping == "raw":
        px = np.clip(a, 0, 255)
    else:
        raise ValueError(mapping)
    return Image.fromarray(px.astype(np.uint8), mode="L")


def main() -> int:
    DST.mkdir(parents=True, exist_ok=True)
    missing = [t for _, t, _, _ in RASTERS if not (SRC / t).exists()]
    if not (SRC / VECTOR).exists():
        missing.append(VECTOR)
    if missing:
        print(f"missing in aligned/: {missing}", file=sys.stderr)
        return 1

    manifest = {"slope_max_deg": SLOPE_MAX_DEG, "layers": {}}
    for lid, tif, png, mapping in RASTERS:
        arr = np.array(Image.open(SRC / tif))
        print(f"{lid}: {tif} {arr.shape} {arr.dtype} min={float(arr.min()):.4f} max={float(arr.max()):.4f}")
        to_png(arr, mapping).save(DST / png)
        size_kb = (DST / png).stat().st_size / 1024
        print(f"  -> {png} ({size_kb:.1f} KB, mapping={mapping})")
        manifest["layers"][lid] = {"file": png, "kind": "raster", "mapping": mapping}

    shutil.copy2(SRC / VECTOR, DST / VECTOR)
    size_mb = (DST / VECTOR).stat().st_size / 1e6
    print(f"copied {VECTOR} ({size_mb:.2f} MB)")
    manifest["layers"]["geology"] = {"file": VECTOR, "kind": "vector"}
    (DST / "layers.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"done -> {DST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
