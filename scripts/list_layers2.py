import pyogrio
gdb = "sim3464_database/database/Geodatabase/Nili.gdb"
layers = pyogrio.list_layers(gdb)
print("LAYERS (name, geomtype):")
for row in layers:
    print(" ", tuple(row))
