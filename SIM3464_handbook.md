# SIM3464 Jezero + Nili Planum — Elevation + Geology Handbook
Repository path: `sim3464_database/sim3464_JezeroNili_FINAL/`
Map: Sun + Stack 2020, `doi:10.3133/sim3464`, 1:75,000, 1x1deg 76.8–77.8E, 17.7–18.7N.
Companion high-res: `MSR_TRN_HiRISE_soc_003_USGS_release_aug2024/mosaics/` 1m DTM + 0.25m ortho, 77.0578–77.3808E, 18.1356–18.5880N.

## 0. What you actually have (yes: elevation + geology)

- Geology: `Geodatabase/Nili.gdb` layer `GeoUnits_v1` (1304 polygons, 14 symbol values) + contacts/structures.
- Elevation wall-to-wall: `Rasters/HRSC/nili_h0988_0000_da4_clip.tif` 75 m.
- Elevation strips: `Rasters/USGS_CTX_Stereo_DTMs/*_20m_DTM.tif` 20.2 m (2 strips only, ~66% valid).
- Imagery wall-to-wall: `Rasters/Caltech_CTX_mosaic_feb2018/Nili_CTX_Mosaic_Beta01_Feb2018_MTM.tif` 5 m + `Rasters/USGS_THEMIS_IR_controlled_mosaic_oct2018/*` 100 m day/night.
- Ortho strips: `Rasters/USGS_CTX_Stereo_DTMs/*_6m_ORTHO.tif` 6.06 m.
- Frames: `MapBoundary`, `LandingEllipse` (77.4298E, 18.4663N, 8.48x8.0 km).

All MTM rasters share top-left (-39528.91, 1108513.82). Only the two CTX-stereo pairs are in a different CRS.

## 1. Directory / file bible

```
sim3464_JezeroNili_FINAL/
  Geodatabase/Nili.gdb/            # FileGDB. Real layers: GeoUnits_v1, GeoContacts, LinearFeatures,
                                   # SurfaceFeatures, LocationFeatures, megabreccia_fig2, CrossSections,
                                   # Figures, Nomenclature, MapBoundary, LandingEllipse, GeoUnitsAnno/FiguresAnno
                                   # *.sr.lock = ArcMap lock junk, ignore. Use Nili.gdb via pyogrio/geopandas.
  Rasters/
    Caltech_CTX_mosaic_feb2018/
      Nili_CTX_Mosaic_Beta01_Feb2018_MTM.tif (+.tfw/.ovr/.aux.xml)
                                   # THE base map. 11870x11294 uint8, 5 m. MTM. ~56x59 km.
    HRSC/
      nili_h0988_0000_da4_clip.tif # THE wall-to-wall DEM. 791x753 int16, 75 m. MTM. nodata -32768.
      nili_h0988_0000_hillshade_clip.tif  # 791x753 uint8, derived: HillShade az=315 alt=45 NO_SHADOWS.
      nili_h0988_0000_hillshade_clip.tif.xml  # proves lineage (ArcGIS 10.6 3D Analyst, 20181129).
      h0988_0000.da4.53.tif        # parent HRSC strip 14121x1596 int16 75 m, much taller than map.
      *.tfw : world file (pixel size + top-left). *.ovr : pyramids. *.aux.xml : stats.
    USGS_CTX_Stereo_DTMs/
      J03_045994_1986_J03_046060_1986_20m_DTM.tif  # 5235x2093 float32 20.2 m. Equirectangular-Mars.
      J03_045994_1986_XN_18N282W_6m_ORTHO.tif      # 17448x6974 uint8 6.06 m, same strip ortho.
      B18_016575_1978_B17_016219_1978_20m_DTM.tif  # 3385x1877 float32 20.2 m.
      B17_016219_1978_XN_17N282W_6m_ORTHO.tif      # 11281x6256 uint8 6.06 m.
      J03*.aux.xml : STATISTICS_MINIMUM -3068.25 MAXIMUM -1373.47 MEAN -2207.53 STDDEV 352.08 VALID 66.41%.
    USGS_THEMIS_IR_controlled_mosaic_oct2018/
      nili_THEMIS_DayIR_Controlled_oct2018.tif    # 594x565 uint8 100 m MTM.
      nili_THEMIS_NightIR_Controlled_oct2018.tif  # same grid, thermophysical companion.
  Metadata/SIM3464_metadata.xml    # FGDC: bbox, abstract, unit list, MTM defines clon 77.5E.
  sim3464_JezeroNili_FINAL.mxd     # ArcMap project (needs ArcMap; QGIS can read GDB+TIF directly).
  CoordinateSystems/ FeatureLayerSymbology/  # empty in this checkout.
```

MSR HiRISE (separate product, same Mars sphere R=3396190):
`MSR_hirise_soc_003_DTM_MOLATopography_DeltaGeoid_1m_Eqc_latTs0_lon0_Blend40.tif` 26816x19144 1 m Equirectangular latTs0 lon0, nodata -32767, heights vs MOLA geoid.
`MSR_hirise_soc_003_Orthomosaic_0.25m_..._First_NoBlend.tif` 0.25 m. Plus `FOM_Confidence` masks: 0=NoData 2=Saturated 3=Suspicious 4=Interpolated 10–14=good 15=manual.

## 2. CRS bible — read this before reprojecting anything

Two projected CRS on the same sphere (a=3396190, b=3396190):

1. MTM_clon77.5E — Transverse Mercator, lat0=0 lon0=77.5 k=1, falseE=N=0, meters.
   Used by: GeoUnits + all vectors, CTX mosaic, HRSC, THEMIS. This is your WORKING CRS.
2. Equirectangular Mars — Plate Carree, lat_ts=0 lon0=180 (!), meters.
   Used by: the 4 CTX-stereo files only. Easting ~= -6.1e6. Do NOT overlay directly.

Geographic: Mars_2000_(Sphere) / GCS_Mars, degrees. Map quad MTM (-39528.9,1049162.1)-(16940.7,1108513.8) = lon/lat (76.8000E,17.6988N)-(77.8017E,18.7011N).

Golden rule: reproject group 2 -> group 1 once, then everything aligns pixel-exact at top-left.

Environment trap on this machine: PostgreSQL/PostGIS sets PROJ_LIB/GDAL_DATA to an old proj.db and rasterio fails with `DATABASE.LAYOUT.VERSION.MINOR=2`. Always clear them first (see recipe 0).

## 3. Vectors — what each layer is

| layer | n | geometry | use |
|---|---|---|---|
| GeoUnits_v1 | 1304 | MultiPolygon | geology proper. cols: unit,name,symbol_noSub,subscript,symbol,ORIG_FID,SHAPE_Length,SHAPE_Area,Color_ID |
| GeoContacts | 2496 | LineString | certain 1666 / approximate 829 / boundary 1 |
| LinearFeatures | 382 | LineString | ridge-crest-t1 176, lineament 98, crater-rim-crest 66, delta-lobe-front 32, fluvial-channel 6, buried-crater-crest 4 |
| SurfaceFeatures | 285 | Polygon | dark-mantle 256, ridged 29 |
| LocationFeatures | 341 | Point | small crater |
| megabreccia_fig2 | 361 | Point | Fig.2 stations, TYPE=megabreccia |
| CrossSections | 2 | LineString | profile A 29.7 km, B 17.7 km |
| Figures | 12 | Polygon | figureNo 3A-3C,4,5A-5C,6A-6B,7A-7C |
| Nomenclature | 10 | anno poly | JEZERO, NILI PLANUM, Neretva Vallis, Una Vallis, Angelica/Belva/Hartwell/Marysville/Sedona/Ulricehamn |
| MapBoundary | 1 | Polygon | quad + LAT_MIN/MAX LON_MIN/MAX CLON |
| LandingEllipse | 1 | Polygon | Mars2020 W-Jezero ellipse |
| GeoUnitsAnno/FiguresAnno | 1294/… | anno | print labels only, skip for analysis |

Unit census (symbol : count): Aeb:475 Eolian bedform, Nue:269 Upper etched (+1 row mislabeled Nue/Crater-riim — treat `name` as truth, see pitfall), Nnp1:156, Nnp2:128, Nrb:70 Rugged bright, cr:64 (63 rim +1 riim typo), su:53 Smooth undiff, Nle:20 Lower etched, ce:15 ejecta, NHjf2:15 fan2, Njf:13 floor, ci:9 interior, NHjf1:9 fan1, Hnpf:8 Nili fan. `symbol = symbol_noSub+subscript` (e.g. Nnp+1). Group by `name`, not `symbol`, for clean stats.

## 4. Recipe 0 — clean environment + paths (copy-paste header)

```python SIM3464_recipes.py
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
```
Check: `gpd.read_file(GDB, layer="GeoUnits_v1").crs == rasterio.open(HRSC_DTM).crs` -> True. Anchor confirmed.

## 5. Recipe 1 — inventory (vectors + rasters)

```python SIM3464_recipes.py
# ... existing code ...
import pyogrio
print(pyogrio.list_layers(GDB))
for lyr, geom in pyogrio.list_layers(GDB):
    d = gpd.read_file(GDB, layer=lyr)
    print(f"{lyr:18s} {len(d):5d} {str(d.crs)[:50]} cols={list(d.columns)[:6]}")
for f in [HRSC_DTM, HRSC_SHADE, CTX_MOS, THEMIS_DAY, CTX_J03_DTM, CTX_J03_ORT]:
    with rasterio.open(f) as s:
        print(f.split("/")[-1], s.height, "x", s.width, s.dtypes[0], "res=", tuple(round(v,2) for v in s.res), "nodata=", s.nodata)
```

## 6. Recipe 2 — read big rasters windowed (no OOM)

```python SIM3464_recipes.py
# ... existing code ...
from rasterio.windows import from_bounds
with rasterio.open(CTX_MOS) as src:  # 11870x11294, never read()+imshow() full
    thumb = src.read(1, out_shape=(1, 1187, 1129))  # 10x decimated preview
    win = from_bounds(src.bounds.left+20000, src.bounds.bottom+20000,
                      src.bounds.left+30000, src.bounds.bottom+30000, src.transform)
    tile = src.read(1, window=win)  # 2000x2000 tile
```

## 7. Recipe 3 — reproject CTX-stereo Equirect->MTM once

```python SIM3464_recipes.py
# ... existing code ...
from rasterio.warp import calculate_default_transform, reproject, Resampling
import numpy as np
with rasterio.open(CTX_J03_DTM) as src, rasterio.open(HRSC_DTM) as ref:
    tr, w, h = calculate_default_transform(src.crs, ref.crs, src.width, src.height, *src.bounds, resolution=20)
    out = np.empty((h, w), dtype="float32")
    reproject(rasterio.band(src,1), out, src_transform=src.transform, src_crs=src.crs,
              dst_transform=tr, dst_crs=ref.crs, resampling=Resampling.bilinear,
              src_nodata=src.nodata, dst_nodata=-32768)
    with rasterio.open("J03_DTM_MTM_20m.tif","w",driver="GTiff",height=h,width=w,count=1,
                       dtype="float32",crs=ref.crs,transform=tr,nodata=-32768,compress="lzw") as d:
        d.write(out,1)
# ortho: same but Resampling.bilinear uint8 nodata 0; masks: Resampling.nearest
```

## 8. Recipe 4 — dissolve + areas

```python SIM3464_recipes.py
# ... existing code ...
units = gpd.read_file(GDB, layer="GeoUnits_v1")
diss = units.dissolve(by="name", as_index=False)
diss["area_km2"] = diss.geometry.area/1e6
print(diss[["name","area_km2"]].sort_values("area_km2",ascending=False).to_string())
diss.to_file("geounits_dissolved.gpkg", driver="GPKG")
fans = units[units["name"].isin(["Jezero fan 1 unit","Jezero fan 2 unit","Jezero floor unit","Nili Planum fan unit"])]
```

## 9. Recipe 5 — zonal stats + slope

```python SIM3464_recipes.py
# ... existing code ...
from rasterstats import zonal_stats
units_mtm = gpd.read_file(GDB, layer="GeoUnits_v1")  # already MTM
zs = zonal_stats(units_mtm, HRSC_DTM, stats=["min","max","mean","std","count"], nodata=-32768)
units_mtm["h_mean"]=[z["mean"] for z in zs]; units_mtm["h_std"]=[z["std"] for z in zs]
print(units_mtm.groupby("name")[["h_mean","h_std"]].mean().round(1).sort_values("h_mean").to_string())
with rasterio.open(HRSC_DTM) as s:
    dem=s.read(1).astype("float32"); dem[dem==s.nodata]=float("nan")
    gy,gx=np.gradient(dem, s.res[0]); slope=np.degrees(np.arctan(np.hypot(gx,gy)))
```

## 10. Recipe 6 — profiles A-B

```python SIM3464_recipes.py
# ... existing code ...
xs = gpd.read_file(GDB, layer="CrossSections")
with rasterio.open(HRSC_DTM) as s:
    dem=s.read(1).astype(float); dem[dem==s.nodata]=float("nan")
    for _,r in xs.iterrows():
        line=r.geometry; ds=np.arange(0,line.length,75)
        pts=[line.interpolate(d) for d in ds]
        rows,cols=rasterio.transform.rowcol(s.transform,[p.x for p in pts],[p.y for p in pts])
        vals=dem[np.array(rows),np.array(cols)]
```

## 11. Recipe 7 — MSR HiRISE Eqc->MTM

Same as Recipe 3 with `MSR_DTM` (Eqc latTs0 lon0, nodata -32767, 26816x19144). Reproject at 20 m for CTX parity, tile windows for 1 m work.

## 12. Pitfalls

PROJ_LIB stale; Equirect vs MTM shift; symbol vs name typos (`cr/Crater riim`, `Nue/Nnp`); SHAPE_Area stale; nodata zoo (-32768/-3.4e38/-32767/255); .sr.lock junk; vertical datums differ — compare relief/slope, not absolute heights across products without tie-point alignment.

Outputs to generate: `J03_DTM_MTM_20m.tif`, `geounits_dissolved.gpkg`, profiles PNG.

