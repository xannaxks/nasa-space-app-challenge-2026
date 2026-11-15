import geopandas as gpd
gdb = "sim3464_database/database/Geodatabase/Nili.gdb"
for lyr in ["GeoUnits_v1","MapBoundary","GeoContacts","LinearFeatures","SurfaceFeatures","LocationFeatures","LandingEllipse","Nomenclature","CrossSections","Figures","megabreccia_fig2"]:
    try:
        info = gpd.read_file(gdb, layer=lyr, rows=5)
        print("="*70)
        print(f"LAYER {lyr}: n={len(info)} (first 5), cols={list(info.columns)}")
        print(" CRS:", info.crs)
        print(" geomtypes:", info.geom_type.unique().tolist())
        print(info.head(2).to_string())
        # full count + bounds via pyogrio quickly
        import pyogrio
        df = pyogrio.read_dataframe(gdb, layer=lyr)
        print(f" FULL COUNT {len(df)}, bounds {df.get_geometry().total_bounds if len(df)>0 else None}")
    except Exception as e:
        print(f"LAYER {lyr} FAIL: {e}")
