import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import geopandas as gpd
    import matplotlib.pyplot as plt
    from pathlib import Path
    import pyogrio

    return


@app.cell
def _():
    def _():
        import os
        for k in ["PROJ_LIB", "GDAL_DATA"]:
            os.environ.pop(k, None)
        import geopandas as gpd
        from pyproj import CRS, Transformer
        gdb = "sim3464_database/database/Geodatabase/Nili.gdb"
        b = gpd.read_file(gdb, layer="MapBoundary")
        print("crs wkt head:", str(b.crs)[:400])
        mtm = CRS(b.crs)
        geo = mtm.geodetic_crs
        print("geodetic:", geo)
        print("ellipsoid:", geo.ellipsoid)
        tr = Transformer.from_crs(mtm, geo, always_xy=True)
        print("MTM bounds:", b.total_bounds)
        merk = b.total_bounds
        print("lonlat SW:", tr.transform(merk[0], merk[1]))
        print("lonlat NE:", tr.transform(merk[2], merk[3]))
        # CTX DTM check
        import rasterio
        for f in [
         "sim3464_database/sim3464_JezeroNili_FINAL/Rasters/USGS_CTX_Stereo_DTMs/J03_045994_1986_J03_046060_1986_20m_DTM.tif",
         "sim3464_database/sim3464_JezeroNili_FINAL/Rasters/Caltech_CTX_mosaic_feb2018/Nili_CTX_Mosaic_Beta01_Feb2018_MTM.tif",
        ]:
            s = rasterio.open(f)
            print("---", f.split("/")[-1])
            print(" wkt head:", str(s.crs)[:300])
            print(" ellipsoid:", CRS(s.crs).ellipsoid if s.crs else None)

    _()
    return


@app.cell
def _():
    import numpy as np
    import pandas as pd
    import rasterio
    import os
    from pyproj import Transformer
    import copy

    return np, rasterio


@app.cell
def _():
    # gdb = "sim3464_database/database/Geodatabase/Nili.gdb"
    # boundary = gpd.read_file(gdb, layer = 'MapBoundary')

    # boundary_crs = boundary.crs
    # print('Boundary CRS: ', boundary_crs)

    # boundary_total_bounds = boundary.total_bounds
    # print('Boundaries bound: ', boundary_total_bounds)

    # boundary_transformer = Transformer.from_crs(
    #     boundary_crs,
    #     boundary_crs.geodetic_crs,
    #     always_xy = True
    # )
    # print('Boundary transformer: ', boundary_transformer)

    # top_left_lon, top_left_lat = boundary_transformer.transform(boundary_total_bounds[0], boundary_total_bounds[1])
    # bottom_right_lon, bottom_right_lat = boundary_transformer.transform(boundary_total_bounds[2], boundary_total_bounds[3])
    # print('Top left lon and lat: ', top_left_lon, top_left_lat)
    # print('Bottom right lon and lat: ', bottom_right_lon, bottom_right_lat)
    return


@app.cell
def _():
    # def _():
    #     import os
    #     for k in ["PROJ_LIB", "GDAL_DATA"]:
    #         os.environ.pop(k, None)  # PostGIS ships old proj.db -> rasterio fails otherwise
    #     import geopandas as gpd, rasterio

    #     BASE = "sim3464_database/sim3464_JezeroNili_FINAL"
    #     GDB  = f"{BASE}/Geodatabase/Nili.gdb"
    #     HRSC_DTM   = f"{BASE}/Rasters/HRSC/nili_h0988_0000_da4_clip.tif"
    #     HRSC_SHADE = f"{BASE}/Rasters/HRSC/nili_h0988_0000_hillshade_clip.tif"
    #     CTX_MOS    = f"{BASE}/Rasters/Caltech_CTX_mosaic_feb2018/Nili_CTX_Mosaic_Beta01_Feb2018_MTM.tif"
    #     THEMIS_DAY = f"{BASE}/Rasters/USGS_THEMIS_IR_controlled_mosaic_oct2018/nili_THEMIS_DayIR_Controlled_oct2018.tif"
    #     THEMIS_NGT = f"{BASE}/Rasters/USGS_THEMIS_IR_controlled_mosaic_oct2018/nili_THEMIS_NightIR_Controlled_oct2018.tif"
    #     CTX_J03_DTM = f"{BASE}/Rasters/USGS_CTX_Stereo_DTMs/J03_045994_1986_J03_046060_1986_20m_DTM.tif"
    #     CTX_J03_ORT = f"{BASE}/Rasters/USGS_CTX_Stereo_DTMs/J03_045994_1986_XN_18N282W_6m_ORTHO.tif"
    #     CTX_B18_DTM = f"{BASE}/Rasters/USGS_CTX_Stereo_DTMs/B18_016575_1978_B17_016219_1978_20m_DTM.tif"
    #     CTX_B17_ORT = f"{BASE}/Rasters/USGS_CTX_Stereo_DTMs/B17_016219_1978_XN_17N282W_6m_ORTHO.tif"
    #     MSR_DTM = "MSR_TRN_HiRISE_soc_003_USGS_release_aug2024/mosaics/MSR_hirise_soc_003_DTM_MOLATopography_DeltaGeoid_1m_Eqc_latTs0_lon0_Blend40.tif"

    #     # ... existing code ...
    #     import pyogrio
    #     print(pyogrio.list_layers(GDB))
    #     for lyr, geom in pyogrio.list_layers(GDB):
    #         d = gpd.read_file(GDB, layer=lyr)
    #         print(f"{lyr:18s} {len(d):5d} {str(d.crs)[:50]} cols={list(d.columns)[:6]}")
    #     for f in [HRSC_DTM, HRSC_SHADE, CTX_MOS, THEMIS_DAY, CTX_J03_DTM, CTX_J03_ORT]:
    #         with rasterio.open(f) as s:
    #             print(f.split("/")[-1], s.height, "x", s.width, s.dtypes[0], "res=", tuple(round(v,2) for v in s.res), "nodata=", s.nodata)

    # _()
    return


@app.cell
def _():
    # def _():
    #     from matplotlib.patches import Patch

    #     gdb = "sim3464_database/database/Geodatabase/Nili.gdb"
    #     units = gpd.read_file(gdb, layer="GeoUnits_v1")
    #     bnd = gpd.read_file(gdb, layer="MapBoundary")
    #     contacts = gpd.read_file(gdb, layer="GeoContacts")
    #     linear = gpd.read_file(gdb, layer="LinearFeatures")
    #     surf = gpd.read_file(gdb, layer="SurfaceFeatures")
    #     ellipse = gpd.read_file(gdb, layer="LandingEllipse")

    #     # --- Fig 1: geologic units ---
    #     fig, ax = plt.subplots(figsize=(10, 10))
    #     # color by 'unit' code
    #     uniq = sorted(units['unit'].unique())
    #     cmap = plt.get_cmap('tab20', len(uniq))
    #     color_map = {u: cmap(i) for i, u in enumerate(uniq)}
    #     units['__c'] = units['unit'].map(color_map)
    #     units.plot(ax=ax, color=units['__c'], edgecolor='black', linewidth=0.15)
    #     bnd.boundary.plot(ax=ax, color='red', linewidth=1.2)
    #     ellipse.boundary.plot(ax=ax, color='cyan', linewidth=1.2)
    #     ax.set_title("SIM3464 Nili.gdb — GeoUnits_v1 (1304 polys) + MapBoundary (red) + LandingEllipse (cyan)")
    #     ax.set_xlabel("Easting (m, MTM clon77.5E)")
    #     ax.set_ylabel("Northing (m, MTM clon77.5E)")
    #     ax.set_aspect('equal')
    #     handles = [Patch(facecolor=color_map[u], edgecolor='black',
    #                      label=f"{u}: {units[units.unit==u].iloc[0]['symbol']} — {units[units.unit==u].iloc[0]['name']} ({(units[units.unit==u]['SHAPE_Area'].sum()/1e6):.1f} km2)")
    #                for u in uniq]
    #     ax.legend(handles=handles, fontsize=7, loc='upper left', bbox_to_anchor=(1.01, 1.0))
    #     plt.tight_layout()
    #     plt.savefig("nili_geounits.png", dpi=150)
    #     print("saved nili_geounits.png")

    #     # --- Fig 2: contacts + linears + surface over units (light) ---
    #     fig2, ax2 = plt.subplots(figsize=(10, 10))
    #     units.plot(ax=ax2, color='lightgrey', edgecolor='none')
    #     contacts.plot(ax=ax2, color='black', linewidth=0.4)
    #     linear.plot(ax=ax2, color='blue', linewidth=0.5)
    #     surf.boundary.plot(ax=ax2, color='orange', linewidth=0.4)
    #     bnd.boundary.plot(ax=ax2, color='red', linewidth=1.2)
    #     ellipse.boundary.plot(ax=ax2, color='cyan', linewidth=1.2)
    #     ax2.set_title("SIM3464 — GeoContacts (black) + LinearFeatures (blue) + SurfaceFeatures (orange)")
    #     ax2.set_xlabel("Easting (m)")
    #     ax2.set_ylabel("Northing (m)")
    #     ax2.set_aspect('equal')
    #     plt.tight_layout()
    #     plt.show()
    # _()
    return


@app.cell
def _():
    # def _():
    #     # --- 0. Environment fix: PostGIS on this machine ships a stale proj.db, so drop ---
    #     # --- these env vars BEFORE importing rasterio/pyproj, else CRS init fails. ---
    #     import os
    #     for k in ["PROJ_LIB", "GDAL_DATA"]:
    #         os.environ.pop(k, None)  # remove stale PROJ/GDAL data paths if present; ignore if absent
    #     import numpy as np, rasterio, json  # np: arrays/math; rasterio: GeoTIFF I/O + warp; json: sidecar stats/lookup
    #     from rasterio.warp import reproject, Resampling  # reproject: CRS/resample engine; Resampling: bilinear selector
    #     from rasterio.features import rasterize  # rasterize: burn geology polygons onto the raster grid
    #     import geopandas as gpd  # gpd: read FileGDB layers (GeoUnits_v1 etc.)

    #     BASE = "sim3464_database/sim3464_JezeroNili_FINAL"  # root of the SIM3464 map product
    #     GDB = "sim3464_database/database/Geodatabase/Nili.gdb"  # working GDB copy (FINAL copy is locked by *.sr.lock)
    #     B18 = f"{BASE}/Rasters/USGS_CTX_Stereo_DTMs/B18_016575_1978_B17_016219_1978_20m_DTM.tif"  # south CTX DTM strip, Equirect-Mars, ~20.2 m
    #     J03 = f"{BASE}/Rasters/USGS_CTX_Stereo_DTMs/J03_045994_1986_J03_046060_1986_20m_DTM.tif"  # north CTX DTM strip, Equirect-Mars, ~20.2 m
    #     DAY = f"{BASE}/Rasters/USGS_THEMIS_IR_controlled_mosaic_oct2018/nili_THEMIS_DayIR_Controlled_oct2018.tif"  # THEMIS Day IR, MTM 100 m (defines common grid)
    #     NGT = f"{BASE}/Rasters/USGS_THEMIS_IR_controlled_mosaic_oct2018/nili_THEMIS_NightIR_Controlled_oct2018.tif"  # THEMIS Night IR, same MTM 100 m grid as Day
    #     OUT = "aligned"  # output folder for all pixel-aligned products
    #     os.makedirs(OUT, exist_ok=True)  # create OUT if missing; no-op if it already exists

    #     # --- 1. Common grid = THEMIS Day MTM 100 m; every other layer is warped onto this. ---
    #     with rasterio.open(DAY) as ref:  # open Day IR as the reference (anchor) dataset
    #         W, H, DST_TR, DST_CRS = ref.width, ref.height, ref.transform, ref.crs  # W/H: 565x594 px; TR: 100 m affine; CRS: MTM_clon77.5E
    #         day = ref.read(1).astype(np.float32)  # band 1 -> float32 so later scaling/division stays float
    #     print(f"REF grid {W}x{H} {DST_TR} validDay={(day>0).mean():.3f}")  # echo grid + fraction of nonzero Day pixels (~0.994)

    #     with rasterio.open(NGT) as s:  # open Night IR; expected to already sit on the same MTM grid
    #         night = s.read(1).astype(np.float32)  # band 1 -> float32, same shape as day
    #     assert day.shape == night.shape  # fail fast if Day/Night grids ever diverge (they must be 594x565)

    #     # --- Border nodata mask: both Day and Night are 0 on the same 1973 border pixels. ---
    #     nodata_mask = (day == 0) & (night == 0)  # True where BOTH are 0 -> map border, not real signal
    #     print(f"shared nodata px: {nodata_mask.sum()}")  # expect 1973: used to exclude borders from normalization

    #     def warp_dtm(path):  # reproject one Equirectangular CTX DTM strip onto the MTM 100 m grid
    #         with rasterio.open(path) as src:  # open source strip (20.2 m, Equirect Mars, nodata -3.4e38)
    #             dst = np.full((H, W), -9999.0, dtype=np.float32)  # pre-fill destination with -9999 = our DTM nodata
    #             reproject(rasterio.band(src, 1), dst, src_transform=src.transform,  # band 1 source -> dst array
    #                       src_crs=src.crs, dst_transform=DST_TR, dst_crs=DST_CRS,  # Equirect -> MTM_clon77.5E, 100 m cells
    #                       resampling=Resampling.bilinear,  # smooth interpolation: right for continuous elevation
    #                       src_nodata=float(src.nodata), dst_nodata=-9999.0, num_threads=2)  # honor source nodata; mark empty dest cells
    #             return dst  # HxW float32 DTM on the common grid

    #     b18 = warp_dtm(B18)  # south strip reprojected to MTM 100 m
    #     j03 = warp_dtm(J03)  # north strip reprojected to MTM 100 m
    #     m_b18, m_j03 = b18 != -9999.0, j03 != -9999.0  # boolean valid-data masks per strip
    #     print(f"B18 valid frac {m_b18.mean():.4f} range {b18[m_b18].min():.1f}..{b18[m_b18].max():.1f}")  # ~0.26, ~-2776..-1477 m
    #     print(f"J03 valid frac {m_j03.mean():.4f} range {j03[m_j03].min():.1f}..{j03[m_j03].max():.1f}")  # ~0.49, ~-3073..-1383 m
    #     ov = m_b18 & m_j03  # pixels where BOTH strips have data (seam zone)
    #     print(f"DTM overlap {ov.sum()} J03-B18 median bias {np.median(j03[ov]-b18[ov]):.2f} m mean {np.mean(j03[ov]-b18[ov]):.2f}")  # ~38670 px, ~+7 m bias

    #     # --- 2. Mosaic: merge the two warped strips; mean in overlap, nodata (-9999) elsewhere. ---
    #     dtm = np.full((H, W), -9999.0, dtype=np.float32)  # blank mosaic canvas, -9999 = no DTM coverage
    #     dtm[m_b18] = b18[m_b18]  # paste south strip where valid
    #     dtm[m_j03] = j03[m_j03]  # paste north strip where valid (overwrites B18 outside overlap)
    #     dtm[ov] = (b18[ov] + j03[ov]) / 2.0  # in the seam zone average both (keeps the ~7 m bias visible, no feathering at 100 m)
    #     dtm_valid = dtm != -9999.0  # final coverage mask; expect ~0.63 (strips don't cover the full quad)
    #     print(f"mosaic valid frac {dtm_valid.mean():.4f}")  # echo coverage fraction
    #     dtm[~dtm_valid] = np.nan  # set gaps to NaN so gradient/percentile math ignores them cleanly

    #     # --- 3. Normalize everything to 0-1 with robust p2/p98 stretch (outlier-proof). ---
    #     def robust_norm(a, mask, p=(2, 98)):  # generic percent-clip normalizer for IR bands
    #         v = a[mask]  # only valid (non-border) pixels feed the percentiles
    #         lo, hi = np.percentile(v, p)  # robust black/white points (2nd, 98th percentiles)
    #         n = np.clip((a - lo) / (hi - lo), 0, 1)  # linear stretch + clip to [0,1]
    #         n[~mask] = 0  # force nodata/border pixels to exactly 0
    #         return n.astype(np.float32), float(lo), float(hi)  # return normalized band + stretch limits

    #     day_m = ~nodata_mask  # valid-pixel mask for Day (everything except the shared 0-border)
    #     ngt_m = ~nodata_mask  # same mask for Night (borders are identical by construction)
    #     day_n, day_lo, day_hi = robust_norm(day, day_m)  # Day -> 0-1; limits ~56-190 DN
    #     ngt_n, ngt_lo, ngt_hi = robust_norm(night, ngt_m)  # Night -> 0-1; limits ~16-212 DN
    #     v = dtm[dtm_valid]  # valid mosaic elevations only (NaN gaps excluded)
    #     dlo, dhi, dmean, dstd = float(np.percentile(v, 2)), float(np.percentile(v, 98)), float(v.mean()), float(v.std())  # DTM stretch + stats (~-2735..-1763 m)
    #     dtm_n = np.zeros_like(dtm, dtype=np.float32)  # blank 0-1 canvas (gaps stay 0)
    #     dtm_n[dtm_valid] = np.clip((dtm[dtm_valid] - dlo) / (dhi - dlo), 0, 1)  # stretch valid elevations to [0,1]
    #     print(f"DAY p2-98 {day_lo:.0f}-{day_hi:.0f} NIGHT p2-98 {ngt_lo:.0f}-{ngt_hi:.0f} DTM p2-98 {dlo:.1f}-{dhi:.1f} mean {dmean:.1f} std {dstd:.1f}")  # echo all stretch ranges

    #     # --- 3b. Derive slope + hillshade from the mosaicked 100 m DTM (NaN-safe, gaps -> 0). ---
    #     gx, gy = np.gradient(np.where(dtm_valid, dtm, np.nan), 100.0, 100.0)  # x/y elevation gradients (m per m), 100 m spacing; gaps=NaN
    #     slope = np.degrees(np.arctan(np.hypot(gx, gy))).astype(np.float32)  # slope magnitude in degrees: atan(sqrt(gx^2+gy^2))
    #     slope = np.nan_to_num(slope, nan=0.0, posinf=0.0, neginf=0.0)  # kill NaN/inf leaking from gap edges
    #     slope[~dtm_valid] = 0  # gaps have no slope -> exactly 0
    #     az, alt = np.radians(315), np.radians(45)  # sun azimuth NW 315 deg, altitude 45 deg (classic shaded relief)
    #     dzdx, dzdy = np.nan_to_num(gx, nan=0.0) / 100.0, np.nan_to_num(gy, nan=0.0) / 100.0  # NaN-safe gradients normalized by cell size
    #     hs = (np.sin(alt) - np.cos(alt) * (dzdx * np.cos(az) + dzdy * np.sin(az)) / np.sqrt(1 + dzdx**2 + dzdy**2))  # Lambert-ish hillshade 0-1
    #     hs = np.nan_to_num(np.clip(hs, 0, 1), nan=0.0).astype(np.float32)  # clip to [0,1], kill residual NaN
    #     hs[~dtm_valid] = 0  # gaps have no shading -> 0

    #     # --- 4. Geology: burn GeoUnits_v1 polygons onto the SAME 100 m grid (already MTM, no warp). ---
    #     units = gpd.read_file(GDB, layer="GeoUnits_v1")  # 1304 polygons, MTM coords -> aligns natively with DST_TR
    #     codes = {s: i + 1 for i, s in enumerate(sorted(units["symbol"].unique()))}  # symbol -> 1..14 int code (0 reserved for background)
    #     shapes = [(g, codes[s]) for g, s in zip(units.geometry, units["symbol"])]  # (polygon, code) pairs for the burner
    #     geo = rasterize(shapes, out_shape=(H, W), transform=DST_TR, fill=0, dtype=np.uint16)  # paint codes into HxW uint16, 0 outside units
    #     print(f"GeoUnits rasterized: {len(codes)} symbols, cover frac {(geo>0).mean():.4f}")  # expect 14 symbols, ~0.99 cover
    #     with open(f"{OUT}/geounit_lookup.json", "w") as f:  # save code->symbol table, e.g. {"1":"Aeb",...}
    #         json.dump({str(v): k for k, v in codes.items()}, f, indent=2)  # JSON keys must be str, hence str(v)

    #     # --- 5. Write every product as a GeoTIFF with IDENTICAL transform/CRS -> pixel-aligned. ---
    #     profile = dict(driver="GTiff", height=H, width=W, count=1, crs=DST_CRS, transform=DST_TR, compress="lzw", tiled=True)  # shared GTiff template: same grid for all
    #     def write(name, arr, dtype, nodata=None):  # one-line GeoTIFF writer: name + array + dtype + optional nodata tag
    #         p = dict(profile, dtype=dtype)  # copy template, set this file's dtype
    #         if nodata is not None:  # attach nodata tag only when requested (lets viewers mask gaps)
    #             p["nodata"] = nodata  # e.g. -9999.0 for DTM, 0 for normalized/derived layers
    #         with rasterio.open(f"{OUT}/{name}", "w", **p) as d:  # create the file
    #             d.write(arr.astype(dtype), 1)  # write band 1, casting to the declared dtype
    #         print("wrote", name)  # echo progress

    #     write("DTM_CTX_mosaic_MTM100m.tif", np.where(dtm_valid, dtm, -9999), "float32", -9999.0)  # raw mosaic elevations (m), gaps=-9999
    #     write("DTM_CTX_mosaic_MTM100m_norm01.tif", dtm_n, "float32", 0)  # DTM stretched 0-1, gaps=0
    #     write("THEMIS_Day_MTM100m.tif", day, "float32", 0)  # Day IR raw DN (already on grid, no warp needed)
    #     write("THEMIS_Day_MTM100m_norm01.tif", day_n, "float32", 0)  # Day IR 0-1 (p2-98 ~56-190)
    #     write("THEMIS_Night_MTM100m.tif", night, "float32", 0)  # Night IR raw DN (same grid as Day)
    #     write("THEMIS_Night_MTM100m_norm01.tif", ngt_n, "float32", 0)  # Night IR 0-1 (p2-98 ~16-212)
    #     write("DTM_slope_deg_MTM100m.tif", slope, "float32", 0)  # slope in degrees, gaps=0
    #     write("DTM_hillshade_MTM100m.tif", (hs * 255).astype(np.uint8), "uint8", 0)  # hillshade scaled to 0-255 for viewing
    #     write("GeoUnits_MTM100m.tif", geo, "uint16", 0)  # rasterized geology codes 0-14, 0=background

    #     # --- ML-ready stack: 4 bands x float32, all 0-1: [DTMn, DayN, NightN, slope/90]. ---
    #     stack = np.stack([dtm_n, day_n, ngt_n, np.clip(slope / 90, 0, 1).astype(np.float32)])  # stack along axis 0 -> (4,H,W); slope normalized by 90 deg
    #     with rasterio.open(f"{OUT}/STACK_DTM-Day-Night-Slope_MTM100m.tif", "w", driver="GTiff",  # 4-band GTiff, same grid as everything
    #                        height=H, width=W, count=4, crs=DST_CRS, transform=DST_TR,  # identical georeferencing -> pixel-perfect overlay
    #                        dtype="float32", compress="lzw", tiled=True) as d:  # float32 + lossless LZW + tiling
    #         d.write(stack)  # write all 4 bands at once
    #     print("wrote STACK")  # echo progress

    #     stats = dict(grid=dict(width=W, height=H, res_m=100.0, crs=str(DST_CRS),  # provenance: common grid definition
    #                            transform=list(DST_TR), top_left=list(DST_TR * (0, 0))),  # affine as list + top-left corner coords
    #                  dtm=dict(b18_frac=float(m_b18.mean()), j03_frac=float(m_j03.mean()),  # per-strip coverage fractions
    #                           mosaic_frac=float(dtm_valid.mean()), overlap_px=int(ov.sum()),  # merged coverage + seam pixel count
    #                           j03_b18_median_bias=float(np.median(j03[ov] - b18[ov])),  # seam bias kept in mosaic (~+7 m)
    #                           p2=dlo, p98=dhi, mean=dmean, std=dstd),  # DTM stretch limits + global stats
    #                  day=dict(p2=day_lo, p98=day_hi), night=dict(p2=ngt_lo, p98=ngt_hi),  # IR stretch limits
    #                  geounits={str(v): k for k, v in codes.items()})  # duplicate of geounit_lookup.json for convenience
    #     with open(f"{OUT}/alignment_stats.json", "w") as f:  # write the stats sidecar
    #         json.dump(stats, f, indent=2)  # pretty-printed JSON (indent=2)

    #     # --- 6. Quick-look preview PNG: 6 panels proving all layers line up. ---
    #     import matplotlib  # plotting lib (imported late: only needed for the preview, not the data)
    #     matplotlib.use("Agg")  # headless backend: save PNG without opening a window
    #     import matplotlib.pyplot as plt  # pyplot API
    #     fig, ax = plt.subplots(2, 3, figsize=(15, 10))  # 2 rows x 3 cols figure
    #     ax = ax.ravel()  # flatten 2x3 axes array -> 1D list of 6 for easy indexing
    #     ax[0].imshow(np.where(dtm_valid, dtm, np.nan), cmap="terrain", vmin=dlo, vmax=dhi)  # panel 1: raw mosaic DTM in meters
    #     ax[0].set_title("DTM mosaic (m, p2-98)")  # title with stretch note
    #     ax[1].imshow(day, cmap="gray", vmin=day_lo, vmax=day_hi)  # panel 2: Day IR, robust stretch
    #     ax[1].set_title("Day IR")  # title
    #     ax[2].imshow(night, cmap="inferno", vmin=ngt_lo, vmax=ngt_hi)  # panel 3: Night IR, thermal-style colormap
    #     ax[2].set_title("Night IR")  # title
    #     ax[3].imshow(dtm_n, cmap="gray", vmin=0, vmax=1)  # panel 4: normalized DTM 0-1
    #     ax[3].set_title("DTM norm01")  # title
    #     ax[4].imshow(slope, cmap="magma", vmin=0, vmax=np.percentile(slope[dtm_valid], 98))  # panel 5: slope, top clipped at p98
    #     ax[4].set_title("Slope deg")  # title
    #     im = ax[5].imshow(geo, cmap="tab20")  # panel 6: rasterized geology codes, categorical colormap
    #     ax[5].set_title("GeoUnits rasterized")  # title
    #     for a in ax:  # loop over all 6 panels
    #         a.set_xticks([]); a.set_yticks([])  # hide pixel tick labels (cleaner quick-look)
    #     plt.suptitle("Aligned MTM 100m stack (565x594, all pixel-aligned)")  # figure-level caption
    #     plt.tight_layout()  # auto-adjust spacing so titles don't overlap
    #     plt.savefig(f"{OUT}/preview_aligned.png", dpi=110)  # save preview PNG into OUT
    #     print("preview saved")  # echo completion

    # _()
    return


@app.cell
def _():
    # def stats(raster, name: str):
    #     print(f"{str} CRS: ", raster.crs)
    #     print(f"{str} Transform: ", raster.transform)
    #     print(f"{str} Height: ", raster.height)
    #     print(f"{str} Width: ", raster.width)
    #     print(f"{str} Bounds: ", raster.bounds)
    #     print(f"{str} No data: ", raster.nodata)
    #     print("\n")

    # def _():
    #     elevation = rasterio.open('aligned/DTM_CTX_mosaic_MTM100m_norm01.tif')
    #     hillshade = rasterio.open('aligned/DTM_hillshade_MTM100m.tif')
    #     slope = rasterio.open('aligned/DTM_slope_deg_MTM100m.tif')
    #     day_ir = rasterio.open('aligned/THEMIS_Day_MTM100m_norm01.tif')
    #     night_ir = rasterio.open('aligned/THEMIS_Night_MTM100m_norm01.tif')
    #     geo = rasterio.open('aligned/GeoUnits_MTM100m.tif')

    #     stats(elevation, "Elevation")
    #     stats(hillshade, "Hillshade")
    #     stats(slope, "Slope")
    #     stats(day_ir, "Day IR")
    #     stats(night_ir, "Night IR")
    #     stats(geo, "Geological")
    #     data = geo.read()
    #     print(data)
    #     return plt.imshow(data[0])
    # _()
    return


@app.cell
def _():
    import ast
    import math
    import operator

    BINARY_OPERATORS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
    }

    UNARY_OPERATORS = {
        ast.UAdd: operator.pos,
        ast.USub: operator.neg,
    }

    FUNCTIONS = {
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
        "sqrt": math.sqrt,
        "log": math.log,
        "exp": math.exp,
        "abs": abs,
        "min": min,
        "max": max,
    }


    def compile_expression(expression):

        if len(expression) > 256:
            raise ValueError("Expression too long")

        tree = ast.parse(expression, mode="eval")

        if len(list(ast.walk(tree))) > 50:
            raise ValueError("Expression too complex")

        def evaluate(node, variables):

            if isinstance(node, ast.Constant):
                if type(node.value) not in (int, float):
                    raise ValueError("Only numeric constants allowed")
                return node.value

            if isinstance(node, ast.Name):
                if node.id not in variables:
                    raise ValueError(f"Unknown variable: {node.id}")
                return variables[node.id]

            if isinstance(node, ast.BinOp):
                op_type = type(node.op)

                if op_type not in BINARY_OPERATORS:
                    raise ValueError("Operator not allowed")

                left = evaluate(node.left, variables)
                right = evaluate(node.right, variables)

                if op_type is ast.Pow:
                    if abs(right) > 10:
                        raise ValueError("Exponent too large")

                return BINARY_OPERATORS[op_type](left, right)

            if isinstance(node, ast.UnaryOp):
                op_type = type(node.op)

                if op_type not in UNARY_OPERATORS:
                    raise ValueError("Unary operator not allowed")

                return UNARY_OPERATORS[op_type](
                    evaluate(node.operand, variables)
                )

            if isinstance(node, ast.Call):
                if not isinstance(node.func, ast.Name):
                    raise ValueError("Invalid function")

                name = node.func.id

                if name not in FUNCTIONS or node.keywords:
                    raise ValueError("Function not allowed")

                args = [
                    evaluate(arg, variables)
                    for arg in node.args
                ]

                return FUNCTIONS[name](*args)

            raise ValueError("Invalid expression")

        def function(x):

            result = evaluate(
                tree.body,
                {"x": float(x)}
            )

            if not math.isfinite(result):
                raise ValueError("Non-finite result")

            if result < 0:
                raise ValueError("Negative penalty")

            return result

        return function

    asc_penalty_expr = 0
    desc_penalty_expr = 0
    flat_penalty_expr = 0

    continuous_asc_penalty_expr = 0
    continuous_desc_penalty_expr = 0
    continuous_flat_penalty_expr = 0

    terrain_roughnes_penalty_expr = 0
    thermal_swing_risk_penalty_expr = 0
    obstacle_density_penalty_expr = 0
    terrain_type_IR_based_penalty_expr = 0


    asc_penalty_func = 0
    desc_penalty_func = 0
    flat_penalty_func = 0

    continuous_asc_penalty_func = 0
    continuous_desc_penalty_func = 0
    continuous_flat_penalty_func = 0

    terrain_roughnes_penalty_func = 0
    thermal_swing_risk_penalty_func = 0
    obstacle_density_penalty_func = 0
    terrain_type_IR_based_penalty_func = 0

    terrain_type_geological_based_dict: dict = {}
    return (
        asc_penalty_func,
        continuous_asc_penalty_func,
        continuous_desc_penalty_func,
        desc_penalty_func,
        flat_penalty_func,
        terrain_type_IR_based_penalty_func,
        terrain_type_geological_based_dict,
        thermal_swing_risk_penalty_func,
    )


@app.cell
def _(rasterio):
    def load(params: dict):
        elevation = rasterio.open('aligned/DTM_CTX_mosaic_MTM100m_norm01.tif')
        hillshade = rasterio.open('aligned/DTM_hillshade_MTM100m.tif')
        slope = rasterio.open('aligned/DTM_slope_deg_MTM100m.tif')
        day_ir = rasterio.open('aligned/THEMIS_Day_MTM100m_norm01.tif')
        night_ir = rasterio.open('aligned/THEMIS_Night_MTM100m_norm01.tif')
        geo = rasterio.open('aligned/GeoUnits_MTM100m.tif')

    load({})
    return


@app.cell
def _(INF, calc_cost, height, newi, newj, np, parent, self, width):
    # const int INF = 1000000000;
    # vector<vector<pair<int, int>>> adj;

    # void dijkstra(int s, vector<int> & d, vector<int> & p) {
    #     int n = adj.size();
    #     d.assign(n, INF);
    #     p.assign(n, -1);
    #     vector<bool> u(n, false);

    #     d[s] = 0;
    #     for (int i = 0; i < n; i++) {
    #         int v = -1;
    #         for (int j = 0; j < n; j++) {
    #             if (!u[j] && (v == -1 || d[j] < d[v]))
    #                 v = j;
    #         }

    #         if (d[v] == INF)
    #             break;

    #         u[v] = true;
    #         for (auto edge : adj[v]) {
    #             int to = edge.first;
    #             int len = edge.second;

    #             if (d[v] + len < d[to]) {
    #                 d[to] = d[v] + len;
    #                 p[to] = v;
    #             }
    #         }
    #     }
    # }

    class TraverState:
        def __init__(direction: int, run_distance: float, elevation_change: float):
            self.direction = direction # -1 DESC, 0 flat, 1 ASC
            self.run_distance = run_distance # distance covered without changing direction
            self.elevation_change = elevation_change # current transitions elevation change

    ti = np.array([0, 0, 1, -1, 1, -1, 1, -1])
    tj = np.array([1, -1, 0, 0, 1, -1, -1, 1])

    def get_path(from_i, from_j):
        path = []
        curi = from_i
        curj = from_j

        while True:
            path.append((from_i, from_j))
    
            _to = parent[curi, curj]
            if _to == -1:
                break

            curi += ti[_to]
            curj += tj[_to]

        path.append((curi, curj))    
        path.reverse()
    
        return path

    def dijkstra(_from):
        distance = np.array((height, width), INF)
        parent = np.array((height, width), -1)
        used = np.array((height, width), 0)

        for row, col in _from:
            distance[row, col] = 0

        for _i in range(height):
            for _j in range(width):
                vi = -1
                vj = -1
        
                for __i in range(height):
                    for __j in range(width):
                        if used[__i, __j] == 0 and (vi == -1 or distance[__i, __j] < distance[vi, vj]):
                            vi = __i
                            vj = __j

                if distance[vi, vj] == INF:
                    break

                used[vi, vj] = 1
                for _to in range(8):
                    new_i = vi + ti[_to]
                    new_j = vj + tj[_to]
                    cost = calc_cost(vi, vj, newi, newj)

                    if distance[new_i, new_j] > distance[vi, vj] + cost:
                        distance[new_i, new_j] = distance[vi, vj] + cost
                        parent[new_i, new_j] = _to
                
        return distance

    return


@app.cell
def _(
    ELEVATION_DIRECTION_THRESHOLD,
    W_CONTINUOUS_ELEVATION,
    W_ELEVATION,
    W_OBSTACLES,
    W_ROUGHNESS,
    W_TERRAIN_GEOLOGY,
    W_TERRAIN_IR,
    W_THERMAL,
    asc_penalty_func,
    continuous_asc_penalty_func,
    continuous_desc_penalty_func,
    day_ir,
    desc_penalty_func,
    elevation,
    flat_penalty_func,
    geo,
    get_distance,
    get_roughness_cost,
    night_ir,
    np,
    terrain_type_IR_based_penalty_func,
    terrain_type_geological_based_dict: dict,
    thermal_swing_risk_penalty_func,
):
    from dataclasses import dataclass

    @dataclass
    class TraverseState:
        direction: int = 0       # -1 descending, 0 flat, +1 ascending
        run_distance: float = 0.0
        run_elevation_change: float = 0.0


    @dataclass
    class EdgeInfo:
        elevation_change: float  # signed elevation difference, in meters
        slope_angle: float       # absolute slope angle, in degrees
        direction: int
        distance: float

        def get_distance(from_cell, to_cell):
            from_xy = np.asarray(geo.xy(from_cell), dtype=float)
            to_xy = np.asarray(geo.xy(to_cell), dtype=float)

            return float(np.linalg.norm(to_xy - from_xy))


    def get_edge_info(from_cell, to_cell):
        distance = get_distance(from_cell, to_cell)

        dh = float(elevation[to_cell] - elevation[from_cell])

        if distance == 0:
            raise ValueError("Adjacent cells must have nonzero distance")

        slope_angle = np.degrees(np.arctan2(abs(dh), distance))

        # Ignore tiny elevation fluctuations.
        if dh > ELEVATION_DIRECTION_THRESHOLD:
            direction = 1
        elif dh < -ELEVATION_DIRECTION_THRESHOLD:
            direction = -1
        else:
            direction = 0

        return EdgeInfo(
            elevation_change=dh,
            slope_angle=slope_angle,
            direction=direction,
            distance=distance
        )

    def get_traverse_state(previous_state, edge):
        if edge.direction == 0:
            return TraverseState()

        if edge.direction == previous_state.direction:
            return TraverseState(
                direction=edge.direction,
                run_distance=previous_state.run_distance + edge.distance,
                run_elevation_change=(
                    previous_state.run_elevation_change + abs(edge.elevation_change)
                )
            )

        # Direction changed: begin a new continuous run.
        return TraverseState(
            direction=edge.direction,
            run_distance=edge.distance,
            run_elevation_change=abs(edge.elevation_change)
        )

    def get_elevation_cost(edge):
        if edge.direction == -1:
            return desc_penalty_func(edge.slope_angle)

        if edge.direction == 0:
            return flat_penalty_func(edge.slope_angle)

        return asc_penalty_func(edge.slope_angle)

    def get_continuous_elevation_cost(previous_state, new_state):
        if new_state.direction == -1:
            old_penalty = continuous_desc_penalty_func(
                previous_state.run_distance
            )
            new_penalty = continuous_desc_penalty_func(
                new_state.run_distance
            )

        elif new_state.direction == 1:
            old_penalty = continuous_asc_penalty_func(
                previous_state.run_distance
            )
            new_penalty = continuous_asc_penalty_func(
                new_state.run_distance
            )

        else:
            return 0.0

        return max(0.0, new_penalty - old_penalty)


    def get_rougness_cost(to_cell):
        pass

    def get_terrain_type_geological_based_cost(cell):
        geo_val = geo[cell]
        return terrain_type_geological_based_dict[geo_val]

    def get_thermal_swing_risk_cost(cell):
        return thermal_swing_risk_penalty_func(day_ir[cell] - night_ir[cell])

    def get_obstacle_density_cost(to_cell):
        pass

    def get_terrain_type_IR_based_cost(cell):
        return terrain_type_IR_based_penalty_func(day_ir[cell] - night_ir[cell])

    def calc_cost(from_cell, to_cell, previous_state):

        edge = get_edge_info(from_cell, to_cell)

        new_state = get_traverse_state(previous_state, edge)

        # Edge-based penalties
        elevation_cost = get_elevation_cost(edge)

        continuous_cost = get_continuous_elevation_cost(
            previous_state,
            new_state
        )

        # Cell-based penalties
        terrain_geology_cost = get_terrain_type_geological_based_cost(to_cell)
        terrain_IR_cost = get_terrain_type_IR_based_cost(to_cell)
        roughness_cost = get_roughness_cost(to_cell)
        obstacle_density_cost = get_obstacle_density_cost(to_cell)
        thermal_swing_cost = get_thermal_swing_risk_cost(to_cell)

        local_penalties = (
            W_ELEVATION * elevation_cost
            + W_ROUGHNESS * roughness_cost
            + W_TERRAIN_GEOLOGY * terrain_geology_cost
            + W_TERRAIN_IR * terrain_IR_cost
            + W_THERMAL * thermal_swing_cost
            + W_OBSTACLES * obstacle_density_cost
        )

        # Local penalties are dimensionless.
        base_cost = edge.distance * (1.0 + local_penalties)

        # Continuity cost is an incremental, cumulative cost.
        total_cost = (
            base_cost
            + W_CONTINUOUS_ELEVATION * continuous_cost
        )

        return total_cost, new_state

    return (calc_cost,)


@app.cell
def _():
    # def get_distance(from_cell, to_cell):
    #     from_coor = geo.xy(from_cell)
    #     to_coor = geo.xy(to_cell)
    
    #     euclidean_dist = np.linalg.norm(to_coor - from_coor)
    #     return euclidean_dist

    # def get_traverse_state(from_cell, to_cell, from_traverse_state):
    #     traverse_state = copy.deepcopy(from_traverse_state)

    #     traverse_state.elevation_change = elevation[to_cell] - elevation[from_cell]
    
    #     if traverse_state.elevation_change < 0:
    #         if traverse_state.direction != -1:
    #             traverse_state.direction = -1
    #             traverse_state.run_distance = get_distance(from_cell, to_cell)
    #         else:
    #             traverse_state.run_distance += get_distance(from_cell, to_cell)
    #         traverse_state.elevation_change = -traverse_state.elevation_change
        
    #     if traverse_state.elevation_change == 0:
    #         if traverse_state.direction != 0:
    #             traverse_state.direction = 0
    #             traverse_state.run_distance = get_distance(from_cell, to_cell)
    #         else:
    #             traverse_state.run_distance += get_distance(from_cell, to_cell)
        
    #     if traverse_state.elevation_change > 0:
    #         if traverse_state.direction != 1:
    #             traverse_state.direction = 1
    #             traverse_state.run_distance = get_distance(from_cell, to_cell)
    #         else:
    #             traverse_state.run_distance += get_distance(from_cell, to_cell)
            
    #     return traverse_state

    # def get_elevation_cost(traverse_state):
    #     if traverse_state.direction == -1:
    #         return desc_penalty_func(traverse_state.elevation_change)
    
    #     if traverse_state.direction == 0:
    #         return flat_penalty_func(traverse_state.elevation_change)

    #     return asc_penalty_func(traverse_state.elevation_change)
    
    # def get_continuous_elevation_cost(from_cell, to_cell, traverse_state):
    #     if traverse_state.direction == -1:
    #         return continuous_desc_penalty_func(traverse_state.run_distance)

    #     if traverse_state.direction == 0:
    #         return continuous_flat_penalty_func(traverse_state.run_distance)

    #     return continuous_asc_penalty_func(traverse_state.run_distance)

    # def get_rougness_cost(to_cell):
    #     pass

    # def get_terrain_type_geological_based_cost(cell):
    #     geo_val = geo[cell]
    #     return terrain_type_geological_based_dict[geo_val]

    # def get_thermal_swing_risk_cost(cell):
    #     return thermal_swing_risk_penalty_func(day_ir[cell] - night_ir[cell])

    # def get_obstacle_density_cost(to_cell):
    #     pass

    # def get_terrain_type_IR_based_cost(cell):
    #     return terrain_type_IR_based_penalty_func(day_ir[cell] - night_ir[cell])

    # def calc_cost(from_cell, to_cell, traverse_state):

    #     distance = get_distance(from_cell, to_cell)
    
    #     elevation_cost = get_elevation_cost(traverse_state)
    #     continuous_elevetaion_cost = get_continuous_elevation_cost(traverse_state)
    
    #     terrain_geology_cost = get_terrain_type_geological_based_cost(to_cell)
    #     terrain_IR_cost = get_terrain_type_IR_based_cost(to_cell)
    
    #     thermal_swing_cost = get_thermal_swing_cost(from_cell, to_cell)
    
    #     roughness_cost = get_roughness_cost(to_cell)
    #     obstacle_density_cost = get_obstacle_density_cost(to_cell)

    #     penalties = (
    #         W_ELEVATION * elevation_cost +
    #         W_CONTINUOUS_ELEVATION * continuous_elevetaion_cost
    #         W_ROUGHNESS * roughness_cost +
    #         W_TERRAIN_GEOLOGY * terrain_geology_cost +
    #         W_TERRAIN_IR * terrain_IR_cost +
    #         W_THERMAL * thermal_swing_cost +
    #         W_OBSTACLES * obstacle_density_cost 
    #     )

    #     return distance * (1.0 + penalties)
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
