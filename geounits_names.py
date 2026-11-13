import os
for k in ["PROJ_LIB", "GDAL_DATA"]:
    os.environ.pop(k, None)
import geopandas as gpd
gdb = "sim3464_database/database/Geodatabase/Nili.gdb"
u = gpd.read_file(gdb, layer="GeoUnits_v1")
print(u[["symbol", "name", "symbol_noSub"]].drop_duplicates().sort_values("symbol").to_string())
print("---- names raw ----")
print(sorted(u["name"].unique()))
print("---- symbol_noSub ----")
print(sorted([str(x) for x in u["symbol_noSub"].unique()]))
print(u.groupby(["symbol", "name"]).size())
