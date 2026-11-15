import os
for k in ["PROJ_LIB", "GDAL_DATA"]:
    os.environ.pop(k,None)
print("stub ok")
