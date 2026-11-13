import os
for k in ["PROJ_LIB", "GDAL_DATA"]:
    os.environ.pop(k, None)
import geopandas as gpd
gdb = "sim3464_database/database/Geodatabase/Nili.gdb"
for lyr in ["GeoUnits_v1", "GeoContacts", "MapBoundary", "LandingEllipse"]:
    d = gpd.read_file(gdb, layer=lyr)
    print("====", lyr, len(d), d.crs)
    print(list(d.columns))
    if lyr == "GeoUnits_v1":
        print(d[["symbol", "name"]].drop_duplicates().sort_values("symbol").to_string())
        print(d["symbol"].value_counts().to_string())
