import sys
print(sys.version)
print(sys.executable)
mods = ["geopandas","fiona","osgeo.gdal","osgeo.ogr","rasterio","shapely","pyproj","matplotlib","cv2","numpy","pandas"]
for m in mods:
    try:
        __import__(m)
        print(f"OK {m}")
    except Exception as e:
        print(f"FAIL {m}: {e}")
