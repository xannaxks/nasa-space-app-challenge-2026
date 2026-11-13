import sys, importlib.util
print(sys.version)
# check pyogrio / geopandas io engines
for m in ["pyogrio","geopandas","shapely","pyproj"]:
    try:
        mod=__import__(m)
        print(m, getattr(mod,"__version__", "?"), getattr(mod,"__file__",""))
    except Exception as e:
        print("FAIL",m,e)
try:
    import geopandas as gpd
    print("geopandas io engines test")
    print(gpd.__version__)
except Exception as e:
    print(e)
