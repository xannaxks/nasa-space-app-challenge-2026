import os
for k in ["PROJ_LIB", "GDAL_DATA"]:
    os.environ.pop(k, None)
import geopandas as gpd
import rasterio
from rasterio.windows import from_bounds

# 1. vector-raster CRS match check
gdb = "sim3464_database/database/Geodatabase/Nili.gdb"
units = gpd.read_file(gdb, layer="GeoUnits_v1")
hrsc = rasterio.open("sim3464_database/sim3464_JezeroNili_FINAL/Rasters/HRSC/nili_h0988_0000_da4_clip.tif")
print("units CRS == HRSC CRS ?", units.crs == hrsc.crs)
print("units bounds:", units.total_bounds)
print("hrsc bounds:", hrsc.bounds)

# 2. windowed read of huge CTX mosaic (no OOM)
ctx = rasterio.open("sim3464_database/sim3464_JezeroNili_FINAL/Rasters/Caltech_CTX_mosaic_feb2018/Nili_CTX_Mosaic_Beta01_Feb2018_MTM.tif")
print("CTX full:", ctx.height, ctx.width)
# read 2000x2000 window around center instead of full 11870x11294
win = from_bounds(ctx.bounds.left+20000, ctx.bounds.bottom+20000,
                  ctx.bounds.left+30000, ctx.bounds.bottom+30000, ctx.transform)
arr = ctx.read(1, window=win)
print("window sample:", arr.shape, arr.dtype, arr.min(), arr.max())

# 3. quick dissolve count -> proves aggregation path
print(units.groupby("symbol").size().sort_values(ascending=False).head(10))
