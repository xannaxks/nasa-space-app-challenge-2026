"""Export GeoUnits_v1 as one aggregated, aligned vector map (GeoJSON).

Source:  sim3464_database/database/Geodatabase/Nili.gdb :: GeoUnits_v1
         (1304 MultiPolygon features; CRS is already MTM_clon77.5E)
Reference grid: aligned/THEMIS_Day_MTM100m.tif  (common 565x594 MTM 100 m grid)
Output:  aligned/GeoUnits_vector_MTM100m.geojson (+ stats sidecar)

What it does:
  1. Loads GeoUnits_v1 with ALL native columns preserved
     (unit, name, symbol_noSub, subscript, symbol, ORIG_FID,
      SHAPE_Length, SHAPE_Area, Color_ID, geometry).
  2. make_valid() repair (2/1304 invalid in source), keeps count at 1304.
  3. Confirms / reprojects to the reference raster CRS (MTM_clon77.5E).
     No-op when already equal -- vectors are natively MTM, so they are
     already pixel-aligned with GeoUnits_MTM100m.tif.
  4. Joins integer raster ``_code`` (1..14) from aligned/geounit_lookup.json
     via the ``symbol`` column, so vector <-> raster codes always agree.
  5. Writes a single GeoJSON + a stats sidecar for the frontend/API.

Run:  python export_geology_vector.py
"""

from __future__ import annotations

import json
import os
import time

# PostGIS on this machine ships a stale proj.db -> pop BEFORE geopandas/rasterio.
for _k in ("PROJ_LIB", "GDAL_DATA"):
    os.environ.pop(_k, None)

from pathlib import Path

ALIGNED_DIR = Path("aligned")
GDB = Path("sim3464_database/database/Geodatabase/Nili.gdb")
LAYER = "GeoUnits_v1"
REF_RASTER = ALIGNED_DIR / "THEMIS_Day_MTM100m.tif"
LOOKUP_JSON = ALIGNED_DIR / "geounit_lookup.json"
OUT_GEOJSON = ALIGNED_DIR / "GeoUnits_vector_MTM100m.geojson"
OUT_SIMPLIFIED = ALIGNED_DIR / "GeoUnits_vector_MTM100m_simplified.geojson"
OUT_STATS = ALIGNED_DIR / "GeoUnits_vector_MTM100m_stats.json"
SIMPLIFY_TOL_M = 25.0  # frontend variant; full-res file stays untouched


def main() -> None:
    import geopandas as gpd  # noqa: E402

    started = time.perf_counter()
    print(f"[export] layer {LAYER} from {GDB}")
    gdf = gpd.read_file(GDB, layer=LAYER)
    print(f"[export] loaded {len(gdf)} features, crs={gdf.crs!r}"[:300])
    print(f"[export] columns: {list(gdf.columns)}")
    print(f"[export] geom types: {gdf.geometry.geom_type.value_counts().to_dict()}")

    # --- repair (2/1304 invalid in source) ---
    n_invalid_before = int((~gdf.is_valid).sum())
    if n_invalid_before:
        try:
            gdf["geometry"] = gpd.make_valid(gdf["geometry"])
        except Exception:
            gdf["geometry"] = gdf["geometry"].buffer(0)
        n_invalid_after = int((~gdf.is_valid).sum())
        print(f"[export] make_valid: {n_invalid_before} -> {n_invalid_after} invalid")
    else:
        print("[export] all geometries valid")

    # --- align to reference grid CRS (native MTM: expect no-op) ---
    ref_crs = None
    try:
        import rasterio  # noqa: E402

        with rasterio.open(REF_RASTER) as _ref:
            ref_crs = _ref.crs
        print(f"[export] ref {REF_RASTER.name} crs={ref_crs!r}"[:200])
    except Exception as exc:  # rasterio missing/unreadable -> fall back to GDB CRS
        print(f"[export] WARN: cannot read ref raster ({exc}); keeping GDB CRS")
    if ref_crs is not None and gdf.crs is not None and gdf.crs != ref_crs:
        print("[export] reprojecting vector to reference CRS ...")
        gdf = gdf.to_crs(ref_crs)
    else:
        print("[export] CRS already aligned (no reprojection needed)")

    # --- join raster _code (1..14) via symbol <-> lookup ---
    lookup: dict[str, str] = json.loads(LOOKUP_JSON.read_text(encoding="utf-8"))
    symbol_to_code = {sym: int(code) for code, sym in lookup.items()}
    gdf["_layer"] = LAYER
    gdf["_code"] = gdf["symbol"].map(symbol_to_code)
    missing = gdf[gdf["_code"].isna()]
    if len(missing):
        raise ValueError(
            f"symbols without lookup code: {sorted(missing['symbol'].unique().tolist())}"
        )
    gdf["_code"] = gdf["_code"].astype(int)
    print(f"[export] codes: {sorted(gdf['_code'].unique().tolist())}")

    # --- write single aggregated GeoJSON (all metadata preserved) ---
    # NOTE: GeoJSON has no MTM CRS code, so geopandas writes no "crs" member.
    # Coordinates are MTM metres as-is (same grid as GeoUnits_MTM100m.tif);
    # readers must NOT assume the GeoJSON default (EPSG:4326).
    OUT_GEOJSON.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(OUT_GEOJSON, driver="GeoJSON")
    print(f"[export] wrote {OUT_GEOJSON} ({OUT_GEOJSON.stat().st_size / 1e6:.1f} MB)")

    # --- simplified frontend variant (same features/columns, fewer verts) ---
    simp = gdf.copy()
    simp["geometry"] = simp.geometry.simplify(SIMPLIFY_TOL_M, preserve_topology=True)
    simp.to_file(OUT_SIMPLIFIED, driver="GeoJSON")
    print(
        f"[export] wrote {OUT_SIMPLIFIED} ({OUT_SIMPLIFIED.stat().st_size / 1e6:.1f} MB, "
        f"tol={SIMPLIFY_TOL_M} m)"
    )

    # --- stats sidecar (frontend legend + API /maps/geology/vector/info) ---
    stats = {
        "layer": LAYER,
        "source": str(GDB),
        "files": {
            "full": OUT_GEOJSON.name,
            "simplified": OUT_SIMPLIFIED.name,
            "simplify_tol_m": SIMPLIFY_TOL_M,
        },
        "reference_grid": {
            "raster": REF_RASTER.name,
            "crs": str(ref_crs) if ref_crs is not None else str(gdf.crs),
        },
        "crs": str(gdf.crs),
        "features": int(len(gdf)),
        "invalid_before": int(n_invalid_before),
        "bounds_mtm": [float(v) for v in gdf.total_bounds.tolist()],
        "columns": list(gdf.columns),
        "symbols": sorted(gdf["symbol"].unique().tolist()),
        "codes": sorted(int(c) for c in gdf["_code"].unique().tolist()),
        "count_by_symbol": {str(k): int(v) for k, v in gdf["symbol"].value_counts().items()},
        "area_km2_by_symbol": {
            str(k): round(float(v) / 1e6, 2)
            for k, v in gdf.groupby("symbol")["SHAPE_Area"].sum().items()
        },
        "note": "cr keeps both source name variants ('Crater rim unit' + 'Crater riim unit' typo); "
        "polygon borders ARE the unit contacts (GeoContacts is a separate line layer, not merged).",
    }
    OUT_STATS.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print(f"[export] wrote {OUT_STATS}")

    # --- verify round-trip ---
    check = gpd.read_file(OUT_GEOJSON)
    assert len(check) == len(gdf), f"round-trip count {len(check)} != {len(gdf)}"
    assert set(check["_code"].unique().tolist()) == set(gdf["_code"].unique().tolist())
    print(f"[export] verified {len(check)} features in {time.perf_counter() - started:.1f}s OK")


if __name__ == "__main__":
    main()
