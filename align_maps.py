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
