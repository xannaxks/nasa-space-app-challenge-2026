import pyogrio
gdb = "sim3464_database/database/Geodatabase/Nili.gdb"
layers = pyogrio.list_layers(gdb)
print(layers)
for name, geom, n in layers:
    print(f"LAYER: {name!r} geom={geom} nfeat={n}")
