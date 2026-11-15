import os
for k in ["PROJ_LIB", "GDAL_DATA"]:
    os.environ.pop(k, None)
import numpy as np, rasterio
from rasterio.warp import reproject, Resampling
from rasterio.features import rasterize
import geopandas as gpd

BASE = "sim3464_database/sim3464_JezeroNili_FINAL"
GDB = "sim3464_database/database/Geodatabase/Nili.gdb"
B18 = f"{BASE}/Rasters/USGS_CTX_Stereo_DTMs/B18_016575_1978_B17_016219_1978_20m_DTM.tif"
J03 = f"{BASE}/Rasters/USGS_CTX_Stereo_DTMs/J03_045994_1986_J03_046060_1986_20m_DTM.tif"
DAY = f"{BASE}/Rasters/USGS_THEMIS_IR_controlled_mosaic_oct2018/nili_THEMIS_DayIR_Controlled_oct2018.tif"
NGT = f"{BASE}/Rasters/USGS_THEMIS_IR_controlled_mosaic_oct2018/nili_THEMIS_NightIR_Controlled_oct2018.tif"
print("align stub")
