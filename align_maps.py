# --- 0. Environment fix: PostGIS on this machine ships a stale proj.db, so drop ---
# --- these env vars BEFORE importing rasterio/pyproj, else CRS init fails. ---
import os
for k in ["PROJ_LIB", "GDAL_DATA"]:
    os.environ.pop(k, None)  # remove stale PROJ/GDAL data paths if present; ignore if absent
import numpy as np, rasterio, json  # np: arrays/math; rasterio: GeoTIFF I/O + warp; json: sidecar stats/lookup
from rasterio.warp import reproject, Resampling  # reproject: CRS/resample engine; Resampling: bilinear selector
from rasterio.features import rasterize  # rasterize: burn geology polygons onto the raster grid
import geopandas as gpd  # gpd: read FileGDB layers (GeoUnits_v1 etc.)

BASE = "sim3464_database/sim3464_JezeroNili_FINAL"  # root of the SIM3464 map product
GDB = "sim3464_database/database/Geodatabase/Nili.gdb"  # working GDB copy (FINAL copy is locked by *.sr.lock)
B18 = f"{BASE}/Rasters/USGS_CTX_Stereo_DTMs/B18_016575_1978_B17_016219_1978_20m_DTM.tif"  # south CTX DTM strip, Equirect-Mars, ~20.2 m
J03 = f"{BASE}/Rasters/USGS_CTX_Stereo_DTMs/J03_045994_1986_J03_046060_1986_20m_DTM.tif"  # north CTX DTM strip, Equirect-Mars, ~20.2 m
DAY = f"{BASE}/Rasters/USGS_THEMIS_IR_controlled_mosaic_oct2018/nili_THEMIS_DayIR_Controlled_oct2018.tif"  # THEMIS Day IR, MTM 100 m (defines common grid)
NGT = f"{BASE}/Rasters/USGS_THEMIS_IR_controlled_mosaic_oct2018/nili_THEMIS_NightIR_Controlled_oct2018.tif"  # THEMIS Night IR, same MTM 100 m grid as Day
OUT = "aligned"  # output folder for all pixel-aligned products
os.makedirs(OUT, exist_ok=True)  # create OUT if missing; no-op if it already exists

# --- 1. Common grid = THEMIS Day MTM 100 m; every other layer is warped onto this. ---
with rasterio.open(DAY) as ref:  # open Day IR as the reference (anchor) dataset
    W, H, DST_TR, DST_CRS = ref.width, ref.height, ref.transform, ref.crs  # W/H: 565x594 px; TR: 100 m affine; CRS: MTM_clon77.5E
    day = ref.read(1).astype(np.float32)  # band 1 -> float32 so later scaling/division stays float
print(f"REF grid {W}x{H} {DST_TR} validDay={(day>0).mean():.3f}")  # echo grid + fraction of nonzero Day pixels (~0.994)

with rasterio.open(NGT) as s:  # open Night IR; expected to already sit on the same MTM grid
    night = s.read(1).astype(np.float32)  # band 1 -> float32, same shape as day
assert day.shape == night.shape  # fail fast if Day/Night grids ever diverge (they must be 594x565)

# --- Border nodata mask: both Day and Night are 0 on the same 1973 border pixels. ---
nodata_mask = (day == 0) & (night == 0)  # True where BOTH are 0 -> map border, not real signal
print(f"shared nodata px: {nodata_mask.sum()}")  # expect 1973: used to exclude borders from normalization

def warp_dtm(path):  # reproject one Equirectangular CTX DTM strip onto the MTM 100 m grid
    with rasterio.open(path) as src:  # open source strip (20.2 m, Equirect Mars, nodata -3.4e38)
        dst = np.full((H, W), -9999.0, dtype=np.float32)  # pre-fill destination with -9999 = our DTM nodata
        reproject(rasterio.band(src, 1), dst, src_transform=src.transform,  # band 1 source -> dst array
                  src_crs=src.crs, dst_transform=DST_TR, dst_crs=DST_CRS,  # Equirect -> MTM_clon77.5E, 100 m cells
                  resampling=Resampling.bilinear,  # smooth interpolation: right for continuous elevation
                  src_nodata=float(src.nodata), dst_nodata=-9999.0, num_threads=2)  # honor source nodata; mark empty dest cells
        return dst  # HxW float32 DTM on the common grid

b18 = warp_dtm(B18)  # south strip reprojected to MTM 100 m
j03 = warp_dtm(J03)  # north strip reprojected to MTM 100 m
m_b18, m_j03 = b18 != -9999.0, j03 != -9999.0  # boolean valid-data masks per strip
print(f"B18 valid frac {m_b18.mean():.4f} range {b18[m_b18].min():.1f}..{b18[m_b18].max():.1f}")  # ~0.26, ~-2776..-1477 m
print(f"J03 valid frac {m_j03.mean():.4f} range {j03[m_j03].min():.1f}..{j03[m_j03].max():.1f}")  # ~0.49, ~-3073..-1383 m
ov = m_b18 & m_j03  # pixels where BOTH strips have data (seam zone)
print(f"DTM overlap {ov.sum()} J03-B18 median bias {np.median(j03[ov]-b18[ov]):.2f} m mean {np.mean(j03[ov]-b18[ov]):.2f}")  # ~38670 px, ~+7 m bias

# --- 2. Mosaic: merge the two warped strips; mean in overlap, nodata (-9999) elsewhere. ---
dtm = np.full((H, W), -9999.0, dtype=np.float32)  # blank mosaic canvas, -9999 = no DTM coverage
dtm[m_b18] = b18[m_b18]  # paste south strip where valid
dtm[m_j03] = j03[m_j03]  # paste north strip where valid (overwrites B18 outside overlap)
dtm[ov] = (b18[ov] + j03[ov]) / 2.0  # in the seam zone average both (keeps the ~7 m bias visible, no feathering at 100 m)
dtm_valid = dtm != -9999.0  # final coverage mask; expect ~0.63 (strips don't cover the full quad)
print(f"mosaic valid frac {dtm_valid.mean():.4f}")  # echo coverage fraction
dtm[~dtm_valid] = np.nan  # set gaps to NaN so gradient/percentile math ignores them cleanly

# --- 3. Normalize everything to 0-1 with robust p2/p98 stretch (outlier-proof). ---
def robust_norm(a, mask, p=(2, 98)):  # generic percent-clip normalizer for IR bands
    v = a[mask]  # only valid (non-border) pixels feed the percentiles
    lo, hi = np.percentile(v, p)  # robust black/white points (2nd, 98th percentiles)
    n = np.clip((a - lo) / (hi - lo), 0, 1)  # linear stretch + clip to [0,1]
    n[~mask] = 0  # force nodata/border pixels to exactly 0
    return n.astype(np.float32), float(lo), float(hi)  # return normalized band + stretch limits

day_m = ~nodata_mask  # valid-pixel mask for Day (everything except the shared 0-border)
ngt_m = ~nodata_mask  # same mask for Night (borders are identical by construction)
day_n, day_lo, day_hi = robust_norm(day, day_m)  # Day -> 0-1; limits ~56-190 DN
ngt_n, ngt_lo, ngt_hi = robust_norm(night, ngt_m)  # Night -> 0-1; limits ~16-212 DN
v = dtm[dtm_valid]  # valid mosaic elevations only (NaN gaps excluded)
dlo, dhi, dmean, dstd = float(np.percentile(v, 2)), float(np.percentile(v, 98)), float(v.mean()), float(v.std())  # DTM stretch + stats (~-2735..-1763 m)
dtm_n = np.zeros_like(dtm, dtype=np.float32)  # blank 0-1 canvas (gaps stay 0)
dtm_n[dtm_valid] = np.clip((dtm[dtm_valid] - dlo) / (dhi - dlo), 0, 1)  # stretch valid elevations to [0,1]
print(f"DAY p2-98 {day_lo:.0f}-{day_hi:.0f} NIGHT p2-98 {ngt_lo:.0f}-{ngt_hi:.0f} DTM p2-98 {dlo:.1f}-{dhi:.1f} mean {dmean:.1f} std {dstd:.1f}")  # echo all stretch ranges

# --- 3b. Derive slope + hillshade from the mosaicked 100 m DTM (NaN-safe, gaps -> 0). ---
gx, gy = np.gradient(np.where(dtm_valid, dtm, np.nan), 100.0, 100.0)  # x/y elevation gradients (m per m), 100 m spacing; gaps=NaN
slope = np.degrees(np.arctan(np.hypot(gx, gy))).astype(np.float32)  # slope magnitude in degrees: atan(sqrt(gx^2+gy^2))
slope = np.nan_to_num(slope, nan=0.0, posinf=0.0, neginf=0.0)  # kill NaN/inf leaking from gap edges
slope[~dtm_valid] = 0  # gaps have no slope -> exactly 0
az, alt = np.radians(315), np.radians(45)  # sun azimuth NW 315 deg, altitude 45 deg (classic shaded relief)
dzdx, dzdy = np.nan_to_num(gx, nan=0.0) / 100.0, np.nan_to_num(gy, nan=0.0) / 100.0  # NaN-safe gradients normalized by cell size
hs = (np.sin(alt) - np.cos(alt) * (dzdx * np.cos(az) + dzdy * np.sin(az)) / np.sqrt(1 + dzdx**2 + dzdy**2))  # Lambert-ish hillshade 0-1
hs = np.nan_to_num(np.clip(hs, 0, 1), nan=0.0).astype(np.float32)  # clip to [0,1], kill residual NaN
hs[~dtm_valid] = 0  # gaps have no shading -> 0

# --- 4. Geology: burn GeoUnits_v1 polygons onto the SAME 100 m grid (already MTM, no warp). ---
units = gpd.read_file(GDB, layer="GeoUnits_v1")  # 1304 polygons, MTM coords -> aligns natively with DST_TR
codes = {s: i + 1 for i, s in enumerate(sorted(units["symbol"].unique()))}  # symbol -> 1..14 int code (0 reserved for background)
shapes = [(g, codes[s]) for g, s in zip(units.geometry, units["symbol"])]  # (polygon, code) pairs for the burner
geo = rasterize(shapes, out_shape=(H, W), transform=DST_TR, fill=0, dtype=np.uint16)  # paint codes into HxW uint16, 0 outside units
print(f"GeoUnits rasterized: {len(codes)} symbols, cover frac {(geo>0).mean():.4f}")  # expect 14 symbols, ~0.99 cover
with open(f"{OUT}/geounit_lookup.json", "w") as f:  # save code->symbol table, e.g. {"1":"Aeb",...}
    json.dump({str(v): k for k, v in codes.items()}, f, indent=2)  # JSON keys must be str, hence str(v)

# --- 5. Write every product as a GeoTIFF with IDENTICAL transform/CRS -> pixel-aligned. ---
profile = dict(driver="GTiff", height=H, width=W, count=1, crs=DST_CRS, transform=DST_TR, compress="lzw", tiled=True)  # shared GTiff template: same grid for all
def write(name, arr, dtype, nodata=None):  # one-line GeoTIFF writer: name + array + dtype + optional nodata tag
    p = dict(profile, dtype=dtype)  # copy template, set this file's dtype
    if nodata is not None:  # attach nodata tag only when requested (lets viewers mask gaps)
        p["nodata"] = nodata  # e.g. -9999.0 for DTM, 0 for normalized/derived layers
    with rasterio.open(f"{OUT}/{name}", "w", **p) as d:  # create the file
        d.write(arr.astype(dtype), 1)  # write band 1, casting to the declared dtype
    print("wrote", name)  # echo progress

write("DTM_CTX_mosaic_MTM100m.tif", np.where(dtm_valid, dtm, -9999), "float32", -9999.0)  # raw mosaic elevations (m), gaps=-9999
write("DTM_CTX_mosaic_MTM100m_norm01.tif", dtm_n, "float32", 0)  # DTM stretched 0-1, gaps=0
write("THEMIS_Day_MTM100m.tif", day, "float32", 0)  # Day IR raw DN (already on grid, no warp needed)
write("THEMIS_Day_MTM100m_norm01.tif", day_n, "float32", 0)  # Day IR 0-1 (p2-98 ~56-190)
write("THEMIS_Night_MTM100m.tif", night, "float32", 0)  # Night IR raw DN (same grid as Day)
write("THEMIS_Night_MTM100m_norm01.tif", ngt_n, "float32", 0)  # Night IR 0-1 (p2-98 ~16-212)
write("DTM_slope_deg_MTM100m.tif", slope, "float32", 0)  # slope in degrees, gaps=0
write("DTM_hillshade_MTM100m.tif", (hs * 255).astype(np.uint8), "uint8", 0)  # hillshade scaled to 0-255 for viewing
write("GeoUnits_MTM100m.tif", geo, "uint16", 0)  # rasterized geology codes 0-14, 0=background

# --- ML-ready stack: 4 bands x float32, all 0-1: [DTMn, DayN, NightN, slope/90]. ---
stack = np.stack([dtm_n, day_n, ngt_n, np.clip(slope / 90, 0, 1).astype(np.float32)])  # stack along axis 0 -> (4,H,W); slope normalized by 90 deg
with rasterio.open(f"{OUT}/STACK_DTM-Day-Night-Slope_MTM100m.tif", "w", driver="GTiff",  # 4-band GTiff, same grid as everything
                   height=H, width=W, count=4, crs=DST_CRS, transform=DST_TR,  # identical georeferencing -> pixel-perfect overlay
                   dtype="float32", compress="lzw", tiled=True) as d:  # float32 + lossless LZW + tiling
    d.write(stack)  # write all 4 bands at once
print("wrote STACK")  # echo progress

stats = dict(grid=dict(width=W, height=H, res_m=100.0, crs=str(DST_CRS),  # provenance: common grid definition
                       transform=list(DST_TR), top_left=list(DST_TR * (0, 0))),  # affine as list + top-left corner coords
             dtm=dict(b18_frac=float(m_b18.mean()), j03_frac=float(m_j03.mean()),  # per-strip coverage fractions
                      mosaic_frac=float(dtm_valid.mean()), overlap_px=int(ov.sum()),  # merged coverage + seam pixel count
                      j03_b18_median_bias=float(np.median(j03[ov] - b18[ov])),  # seam bias kept in mosaic (~+7 m)
                      p2=dlo, p98=dhi, mean=dmean, std=dstd),  # DTM stretch limits + global stats
             day=dict(p2=day_lo, p98=day_hi), night=dict(p2=ngt_lo, p98=ngt_hi),  # IR stretch limits
             geounits={str(v): k for k, v in codes.items()})  # duplicate of geounit_lookup.json for convenience
with open(f"{OUT}/alignment_stats.json", "w") as f:  # write the stats sidecar
    json.dump(stats, f, indent=2)  # pretty-printed JSON (indent=2)

# --- 6. Quick-look preview PNG: 6 panels proving all layers line up. ---
import matplotlib  # plotting lib (imported late: only needed for the preview, not the data)
matplotlib.use("Agg")  # headless backend: save PNG without opening a window
import matplotlib.pyplot as plt  # pyplot API
fig, ax = plt.subplots(2, 3, figsize=(15, 10))  # 2 rows x 3 cols figure
ax = ax.ravel()  # flatten 2x3 axes array -> 1D list of 6 for easy indexing
ax[0].imshow(np.where(dtm_valid, dtm, np.nan), cmap="terrain", vmin=dlo, vmax=dhi)  # panel 1: raw mosaic DTM in meters
ax[0].set_title("DTM mosaic (m, p2-98)")  # title with stretch note
ax[1].imshow(day, cmap="gray", vmin=day_lo, vmax=day_hi)  # panel 2: Day IR, robust stretch
ax[1].set_title("Day IR")  # title
ax[2].imshow(night, cmap="inferno", vmin=ngt_lo, vmax=ngt_hi)  # panel 3: Night IR, thermal-style colormap
ax[2].set_title("Night IR")  # title
ax[3].imshow(dtm_n, cmap="gray", vmin=0, vmax=1)  # panel 4: normalized DTM 0-1
ax[3].set_title("DTM norm01")  # title
ax[4].imshow(slope, cmap="magma", vmin=0, vmax=np.percentile(slope[dtm_valid], 98))  # panel 5: slope, top clipped at p98
ax[4].set_title("Slope deg")  # title
im = ax[5].imshow(geo, cmap="tab20")  # panel 6: rasterized geology codes, categorical colormap
ax[5].set_title("GeoUnits rasterized")  # title
for a in ax:  # loop over all 6 panels
    a.set_xticks([]); a.set_yticks([])  # hide pixel tick labels (cleaner quick-look)
plt.suptitle("Aligned MTM 100m stack (565x594, all pixel-aligned)")  # figure-level caption
plt.tight_layout()  # auto-adjust spacing so titles don't overlap
plt.savefig(f"{OUT}/preview_aligned.png", dpi=110)  # save preview PNG into OUT
print("preview saved")  # echo completion
