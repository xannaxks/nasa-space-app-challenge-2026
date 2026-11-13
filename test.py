import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import geopandas as gpd
    import matplotlib.pyplot as plt
    from pathlib import Path
    import pyogrio

    return gpd, plt


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

    return (Transformer,)


@app.cell
def _(Transformer, gpd):
    gdb = "sim3464_database/database/Geodatabase/Nili.gdb"
    boundary = gpd.read_file(gdb, layer = 'MapBoundary')

    boundary_crs = boundary.crs
    print('Boundary CRS: ', boundary_crs)

    boundary_total_bounds = boundary.total_bounds
    print('Boundaries bound: ', boundary_total_bounds)

    boundary_transformer = Transformer.from_crs(
        boundary_crs,
        boundary_crs.geodetic_crs,
        always_xy = True
    )
    print('Boundary transformer: ', boundary_transformer)

    top_left_lon, top_left_lat = boundary_transformer.transform(boundary_total_bounds[0], boundary_total_bounds[1])
    bottom_right_lon, bottom_right_lat = boundary_transformer.transform(boundary_total_bounds[2], boundary_total_bounds[3])
    print('Top left lon and lat: ', top_left_lon, top_left_lat)
    print('Bottom right lon and lat: ', bottom_right_lon, bottom_right_lat)

    return


@app.cell
def _():
    def _():
        import os
        for k in ["PROJ_LIB", "GDAL_DATA"]:
            os.environ.pop(k, None)  # PostGIS ships old proj.db -> rasterio fails otherwise
        import geopandas as gpd, rasterio
    
        BASE = "sim3464_database/sim3464_JezeroNili_FINAL"
        GDB  = f"{BASE}/Geodatabase/Nili.gdb"
        HRSC_DTM   = f"{BASE}/Rasters/HRSC/nili_h0988_0000_da4_clip.tif"
        HRSC_SHADE = f"{BASE}/Rasters/HRSC/nili_h0988_0000_hillshade_clip.tif"
        CTX_MOS    = f"{BASE}/Rasters/Caltech_CTX_mosaic_feb2018/Nili_CTX_Mosaic_Beta01_Feb2018_MTM.tif"
        THEMIS_DAY = f"{BASE}/Rasters/USGS_THEMIS_IR_controlled_mosaic_oct2018/nili_THEMIS_DayIR_Controlled_oct2018.tif"
        THEMIS_NGT = f"{BASE}/Rasters/USGS_THEMIS_IR_controlled_mosaic_oct2018/nili_THEMIS_NightIR_Controlled_oct2018.tif"
        CTX_J03_DTM = f"{BASE}/Rasters/USGS_CTX_Stereo_DTMs/J03_045994_1986_J03_046060_1986_20m_DTM.tif"
        CTX_J03_ORT = f"{BASE}/Rasters/USGS_CTX_Stereo_DTMs/J03_045994_1986_XN_18N282W_6m_ORTHO.tif"
        CTX_B18_DTM = f"{BASE}/Rasters/USGS_CTX_Stereo_DTMs/B18_016575_1978_B17_016219_1978_20m_DTM.tif"
        CTX_B17_ORT = f"{BASE}/Rasters/USGS_CTX_Stereo_DTMs/B17_016219_1978_XN_17N282W_6m_ORTHO.tif"
        MSR_DTM = "MSR_TRN_HiRISE_soc_003_USGS_release_aug2024/mosaics/MSR_hirise_soc_003_DTM_MOLATopography_DeltaGeoid_1m_Eqc_latTs0_lon0_Blend40.tif"

        # ... existing code ...
        import pyogrio
        print(pyogrio.list_layers(GDB))
        for lyr, geom in pyogrio.list_layers(GDB):
            d = gpd.read_file(GDB, layer=lyr)
            print(f"{lyr:18s} {len(d):5d} {str(d.crs)[:50]} cols={list(d.columns)[:6]}")
        for f in [HRSC_DTM, HRSC_SHADE, CTX_MOS, THEMIS_DAY, CTX_J03_DTM, CTX_J03_ORT]:
            with rasterio.open(f) as s:
                print(f.split("/")[-1], s.height, "x", s.width, s.dtypes[0], "res=", tuple(round(v,2) for v in s.res), "nodata=", s.nodata)

    _()
    return


@app.cell
def _(gpd, plt):
    def _():
        from matplotlib.patches import Patch
    
        gdb = "sim3464_database/database/Geodatabase/Nili.gdb"
        units = gpd.read_file(gdb, layer="GeoUnits_v1")
        bnd = gpd.read_file(gdb, layer="MapBoundary")
        contacts = gpd.read_file(gdb, layer="GeoContacts")
        linear = gpd.read_file(gdb, layer="LinearFeatures")
        surf = gpd.read_file(gdb, layer="SurfaceFeatures")
        ellipse = gpd.read_file(gdb, layer="LandingEllipse")
    
        # --- Fig 1: geologic units ---
        fig, ax = plt.subplots(figsize=(10, 10))
        # color by 'unit' code
        uniq = sorted(units['unit'].unique())
        cmap = plt.get_cmap('tab20', len(uniq))
        color_map = {u: cmap(i) for i, u in enumerate(uniq)}
        units['__c'] = units['unit'].map(color_map)
        units.plot(ax=ax, color=units['__c'], edgecolor='black', linewidth=0.15)
        bnd.boundary.plot(ax=ax, color='red', linewidth=1.2)
        ellipse.boundary.plot(ax=ax, color='cyan', linewidth=1.2)
        ax.set_title("SIM3464 Nili.gdb — GeoUnits_v1 (1304 polys) + MapBoundary (red) + LandingEllipse (cyan)")
        ax.set_xlabel("Easting (m, MTM clon77.5E)")
        ax.set_ylabel("Northing (m, MTM clon77.5E)")
        ax.set_aspect('equal')
        handles = [Patch(facecolor=color_map[u], edgecolor='black',
                         label=f"{u}: {units[units.unit==u].iloc[0]['symbol']} — {units[units.unit==u].iloc[0]['name']} ({(units[units.unit==u]['SHAPE_Area'].sum()/1e6):.1f} km2)")
                   for u in uniq]
        ax.legend(handles=handles, fontsize=7, loc='upper left', bbox_to_anchor=(1.01, 1.0))
        plt.tight_layout()
        plt.savefig("nili_geounits.png", dpi=150)
        print("saved nili_geounits.png")
    
        # --- Fig 2: contacts + linears + surface over units (light) ---
        fig2, ax2 = plt.subplots(figsize=(10, 10))
        units.plot(ax=ax2, color='lightgrey', edgecolor='none')
        contacts.plot(ax=ax2, color='black', linewidth=0.4)
        linear.plot(ax=ax2, color='blue', linewidth=0.5)
        surf.boundary.plot(ax=ax2, color='orange', linewidth=0.4)
        bnd.boundary.plot(ax=ax2, color='red', linewidth=1.2)
        ellipse.boundary.plot(ax=ax2, color='cyan', linewidth=1.2)
        ax2.set_title("SIM3464 — GeoContacts (black) + LinearFeatures (blue) + SurfaceFeatures (orange)")
        ax2.set_xlabel("Easting (m)")
        ax2.set_ylabel("Northing (m)")
        ax2.set_aspect('equal')
        plt.tight_layout()
        plt.show()
    _()
    return


@app.cell
def _():
    def _():
        import os
        for k in ["PROJ_LIB", "GDAL_DATA"]:
            os.environ.pop(k, None)
        import numpy as np, rasterio, json
        from rasterio.warp import reproject, Resampling
        from rasterio.features import rasterize
        import geopandas as gpd
    
        BASE = "sim3464_database/sim3464_JezeroNili_FINAL"
        GDB = "sim3464_database/database/Geodatabase/Nili.gdb"
        B18 = f"{BASE}/Rasters/USGS_CTX_Stereo_DTMs/B18_016575_1978_B17_016219_1978_20m_DTM.tif"
        J03 = f"{BASE}/Rasters/USGS_CTX_Stereo_DTMs/J03_045994_1986_J03_046060_1986_20m_DTM.tif"
        DAY = f"{BASE}/Rasters/USGS_THEMIS_IR_controlled_mosaic_oct2018/nili_THEMIS_DayIR_Controlled_oct2018.tif"
        NGT = f"{BASE}/Rasters/USGS_THEMIS_IR_controlled_mosaic_oct2018/nili_THEMIS_NightIR_Controlled_oct2018.tif"
        OUT = "aligned"
        os.makedirs(OUT, exist_ok=True)
    
        # 1. common grid = THEMIS Day MTM 100m
        with rasterio.open(DAY) as ref:
            W, H, DST_TR, DST_CRS = ref.width, ref.height, ref.transform, ref.crs
            day = ref.read(1).astype(np.float32)
        print(f"REF grid {W}x{H} {DST_TR} validDay={(day>0).mean():.3f}")
    
        with rasterio.open(NGT) as s:
            night = s.read(1).astype(np.float32)
        assert day.shape == night.shape
    
        # border nodata mask shared by Day/Night (1973 px, top/bottom rows)
        nodata_mask = (day == 0) & (night == 0)
        print(f"shared nodata px: {nodata_mask.sum()}")
    
        def warp_dtm(path):
            with rasterio.open(path) as src:
                dst = np.full((H, W), -9999.0, dtype=np.float32)
                reproject(rasterio.band(src, 1), dst, src_transform=src.transform,
                          src_crs=src.crs, dst_transform=DST_TR, dst_crs=DST_CRS,
                          resampling=Resampling.bilinear,
                          src_nodata=float(src.nodata), dst_nodata=-9999.0, num_threads=2)
                return dst
    
        b18 = warp_dtm(B18)
        j03 = warp_dtm(J03)
        m_b18, m_j03 = b18 != -9999.0, j03 != -9999.0
        print(f"B18 valid frac {m_b18.mean():.4f} range {b18[m_b18].min():.1f}..{b18[m_b18].max():.1f}")
        print(f"J03 valid frac {m_j03.mean():.4f} range {j03[m_j03].min():.1f}..{j03[m_j03].max():.1f}")
        ov = m_b18 & m_j03
        print(f"DTM overlap {ov.sum()} J03-B18 median bias {np.median(j03[ov]-b18[ov]):.2f} m mean {np.mean(j03[ov]-b18[ov]):.2f}")
    
        # 2. mosaic: mean in overlap (bias ~7m kept visible; feather not needed at 100m)
        dtm = np.full((H, W), -9999.0, dtype=np.float32)
        dtm[m_b18] = b18[m_b18]
        dtm[m_j03] = j03[m_j03]
        dtm[ov] = (b18[ov] + j03[ov]) / 2.0
        dtm_valid = dtm != -9999.0
        print(f"mosaic valid frac {dtm_valid.mean():.4f}")
        dtm[~dtm_valid] = np.nan
    
        # 3. normalize
        def robust_norm(a, mask, p=(2, 98)):
            v = a[mask]
            lo, hi = np.percentile(v, p)
            n = np.clip((a - lo) / (hi - lo), 0, 1)
            n[~mask] = 0
            return n.astype(np.float32), float(lo), float(hi)
    
        day_m = ~nodata_mask
        ngt_m = ~nodata_mask
        day_n, day_lo, day_hi = robust_norm(day, day_m)
        ngt_n, ngt_lo, ngt_hi = robust_norm(night, ngt_m)
        v = dtm[dtm_valid]
        dlo, dhi, dmean, dstd = float(np.percentile(v, 2)), float(np.percentile(v, 98)), float(v.mean()), float(v.std())
        dtm_n = np.zeros_like(dtm, dtype=np.float32)
        dtm_n[dtm_valid] = np.clip((dtm[dtm_valid] - dlo) / (dhi - dlo), 0, 1)
        print(f"DAY p2-98 {day_lo:.0f}-{day_hi:.0f} NIGHT p2-98 {ngt_lo:.0f}-{ngt_hi:.0f} DTM p2-98 {dlo:.1f}-{dhi:.1f} mean {dmean:.1f} std {dstd:.1f}")
    
        # hillshade + slope from mosaicked DTM on 100m grid (NaN-safe, nodata=0)
        gx, gy = np.gradient(np.where(dtm_valid, dtm, np.nan), 100.0, 100.0)
        slope = np.degrees(np.arctan(np.hypot(gx, gy))).astype(np.float32)
        slope = np.nan_to_num(slope, nan=0.0, posinf=0.0, neginf=0.0)
        slope[~dtm_valid] = 0
        az, alt = np.radians(315), np.radians(45)
        dzdx, dzdy = np.nan_to_num(gx, nan=0.0) / 100.0, np.nan_to_num(gy, nan=0.0) / 100.0
        hs = (np.sin(alt) - np.cos(alt) * (dzdx * np.cos(az) + dzdy * np.sin(az)) / np.sqrt(1 + dzdx**2 + dzdy**2))
        hs = np.nan_to_num(np.clip(hs, 0, 1), nan=0.0).astype(np.float32)
        hs[~dtm_valid] = 0
    
        # 4. geology rasterize to same grid
        units = gpd.read_file(GDB, layer="GeoUnits_v1")
        codes = {s: i + 1 for i, s in enumerate(sorted(units["symbol"].unique()))}
        shapes = [(g, codes[s]) for g, s in zip(units.geometry, units["symbol"])]
        geo = rasterize(shapes, out_shape=(H, W), transform=DST_TR, fill=0, dtype=np.uint16)
        print(f"GeoUnits rasterized: {len(codes)} symbols, cover frac {(geo>0).mean():.4f}")
        with open(f"{OUT}/geounit_lookup.json", "w") as f:
            json.dump({str(v): k for k, v in codes.items()}, f, indent=2)
    
        # 5. write GeoTIFFs (all pixel-aligned, same transform/CRS)
        profile = dict(driver="GTiff", height=H, width=W, count=1, crs=DST_CRS, transform=DST_TR, compress="lzw", tiled=True)
        def write(name, arr, dtype, nodata=None):
            p = dict(profile, dtype=dtype)
            if nodata is not None:
                p["nodata"] = nodata
            with rasterio.open(f"{OUT}/{name}", "w", **p) as d:
                d.write(arr.astype(dtype), 1)
            print("wrote", name)
    
        write("DTM_CTX_mosaic_MTM100m.tif", np.where(dtm_valid, dtm, -9999), "float32", -9999.0)
        write("DTM_CTX_mosaic_MTM100m_norm01.tif", dtm_n, "float32", 0)
        write("THEMIS_Day_MTM100m.tif", day, "float32", 0)
        write("THEMIS_Day_MTM100m_norm01.tif", day_n, "float32", 0)
        write("THEMIS_Night_MTM100m.tif", night, "float32", 0)
        write("THEMIS_Night_MTM100m_norm01.tif", ngt_n, "float32", 0)
        write("DTM_slope_deg_MTM100m.tif", slope, "float32", 0)
        write("DTM_hillshade_MTM100m.tif", (hs * 255).astype(np.uint8), "uint8", 0)
        write("GeoUnits_MTM100m.tif", geo, "uint16", 0)
    
        # stacked ML-ready 4-band float32: DTMn, DayN, NightN, slope/90
        stack = np.stack([dtm_n, day_n, ngt_n, np.clip(slope / 90, 0, 1).astype(np.float32)])
        with rasterio.open(f"{OUT}/STACK_DTM-Day-Night-Slope_MTM100m.tif", "w", driver="GTiff",
                           height=H, width=W, count=4, crs=DST_CRS, transform=DST_TR,
                           dtype="float32", compress="lzw", tiled=True) as d:
            d.write(stack)
        print("wrote STACK")
    
        stats = dict(grid=dict(width=W, height=H, res_m=100.0, crs=str(DST_CRS),
                               transform=list(DST_TR), top_left=list(DST_TR * (0, 0))),
                     dtm=dict(b18_frac=float(m_b18.mean()), j03_frac=float(m_j03.mean()),
                              mosaic_frac=float(dtm_valid.mean()), overlap_px=int(ov.sum()),
                              j03_b18_median_bias=float(np.median(j03[ov] - b18[ov])),
                              p2=dlo, p98=dhi, mean=dmean, std=dstd),
                     day=dict(p2=day_lo, p98=day_hi), night=dict(p2=ngt_lo, p98=ngt_hi),
                     geounits={str(v): k for k, v in codes.items()})
        with open(f"{OUT}/alignment_stats.json", "w") as f:
            json.dump(stats, f, indent=2)
    
        # preview
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(2, 3, figsize=(15, 10))
        ax = ax.ravel()
        ax[0].imshow(np.where(dtm_valid, dtm, np.nan), cmap="terrain", vmin=dlo, vmax=dhi)
        ax[0].set_title("DTM mosaic (m, p2-98)")
        ax[1].imshow(day, cmap="gray", vmin=day_lo, vmax=day_hi)
        ax[1].set_title("Day IR")
        ax[2].imshow(night, cmap="inferno", vmin=ngt_lo, vmax=ngt_hi)
        ax[2].set_title("Night IR")
        ax[3].imshow(dtm_n, cmap="gray", vmin=0, vmax=1)
        ax[3].set_title("DTM norm01")
        ax[4].imshow(slope, cmap="magma", vmin=0, vmax=np.percentile(slope[dtm_valid], 98))
        ax[4].set_title("Slope deg")
        im = ax[5].imshow(geo, cmap="tab20")
        ax[5].set_title("GeoUnits rasterized")
        for a in ax:
            a.set_xticks([]); a.set_yticks([])
        plt.suptitle("Aligned MTM 100m stack (565x594, all pixel-aligned)")
        plt.tight_layout()
        plt.savefig(f"{OUT}/preview_aligned.png", dpi=110)
        print("preview saved")
        plt.show()
    _()
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
