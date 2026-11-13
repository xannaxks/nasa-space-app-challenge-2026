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
