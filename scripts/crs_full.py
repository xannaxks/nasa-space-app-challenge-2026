import os
for k in ["PROJ_LIB", "GDAL_DATA"]:
    os.environ.pop(k, None)
import rasterio
from pyproj import CRS
files = {
 "HRSC_DTM": "sim3464_database/sim3464_JezeroNili_FINAL/Rasters/HRSC/nili_h0988_0000_da4_clip.tif",
 "CTX_J03_DTM": "sim3464_database/sim3464_JezeroNili_FINAL/Rasters/USGS_CTX_Stereo_DTMs/J03_045994_1986_J03_046060_1986_20m_DTM.tif",
 "CTX_B18_DTM": "sim3464_database/sim3464_JezeroNili_FINAL/Rasters/USGS_CTX_Stereo_DTMs/B18_016575_1978_B17_016219_1978_20m_DTM.tif",
 "CTX_J03_ORTHO": "sim3464_database/sim3464_JezeroNili_FINAL/Rasters/USGS_CTX_Stereo_DTMs/J03_045994_1986_XN_18N282W_6m_ORTHO.tif",
 "CTX_mosaic": "sim3464_database/sim3464_JezeroNili_FINAL/Rasters/Caltech_CTX_mosaic_feb2018/Nili_CTX_Mosaic_Beta01_Feb2018_MTM.tif",
 "THEMIS_day": "sim3464_database/sim3464_JezeroNili_FINAL/Rasters/USGS_THEMIS_IR_controlled_mosaic_oct2018/nili_THEMIS_DayIR_Controlled_oct2018.tif",
}
for name, f in files.items():
    s = rasterio.open(f)
    print("="*100)
    print(name, f)
    print(s.crs.to_wkt()[:1200])
    print("transform:", s.transform, "shape:", (s.height, s.width))
