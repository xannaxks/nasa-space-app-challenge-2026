import geopandas as gpd
from pyproj import Transformer
gdb = "sim3464_database/database/Geodatabase/Nili.gdb"

def load(lyr):
    df = gpd.read_file(gdb, layer=lyr)
    return df

units = load("GeoUnits_v1")
bnd = load("MapBoundary")
contacts = load("GeoContacts")
linear = load("LinearFeatures")
surf = load("SurfaceFeatures")
loc = load("LocationFeatures")
ellipse = load("LandingEllipse")

print("=== CRS ===")
print(units.crs)
print()
print("geodetic (lon/lat base):", units.crs.geodetic_crs)
print()

for name, df in [("GeoUnits_v1",units),("MapBoundary",bnd),("GeoContacts",contacts),
                 ("LinearFeatures",linear),("SurfaceFeatures",surf),
                 ("LocationFeatures",loc),("LandingEllipse",ellipse)]:
    tb = df.total_bounds  # xmin ymin xmax ymax
    print(f"{name}: n={len(df)} geom={df.geom_type.unique().tolist()} cols={list(df.columns)}")
    print(f"  projected bounds (MTM m): xmin={tb[0]:.1f} ymin={tb[1]:.1f} xmax={tb[2]:.1f} ymax={tb[3]:.1f}")
    print(f"  width={(tb[2]-tb[0])/1000:.2f} km height={(tb[3]-tb[1])/1000:.2f} km")
    print()

# lon/lat conversion via geodetic_crs
geo = units.crs.geodetic_crs
tr = Transformer.from_crs(units.crs, geo, always_xy=True)
for label, x, y in [
    ("MapBoundary SW", bnd.total_bounds[0], bnd.total_bounds[1]),
    ("MapBoundary NE", bnd.total_bounds[2], bnd.total_bounds[3]),
]:
    lon, lat = tr.transform(x, y)
    print(f"{label}: MTM({x:.1f},{y:.1f}) -> lon {lon:.4f}E lat {lat:.4f}N")
cx = (bnd.total_bounds[0]+bnd.total_bounds[2])/2
cy = (bnd.total_bounds[1]+bnd.total_bounds[3])/2
lonc, latc = tr.transform(cx, cy)
print(f"Map center: MTM({cx:.1f},{cy:.1f}) -> lon {lonc:.4f}E lat {latc:.4f}N")

# areas
print()
print("=== AREAS ===")
print(f"MapBoundary SHAPE_Area attr: {float(bnd.iloc[0]['Shape_Area'])/1e6:.2f} km2")
# computed geodesic-ish planar area (m2, MTM meters are true meters)
print(f"MapBoundary computed area: {float(bnd.geometry.area.iloc[0])/1e6:.2f} km2")
print(f"GeoUnits_v1 total polygon area: {float(units.geometry.area.sum())/1e6:.2f} km2 "
      f"({float(units.geometry.area.sum())/1e9:.4f} x10^9 m2)")
print(f"GeoUnits_v1 SHAPE_Area col sum: {float(units['SHAPE_Area'].sum())/1e6:.2f} km2")
print()
print("=== GeoUnits breakdown ===")
print(units[['unit','name','symbol']].drop_duplicates().sort_values('unit').to_string())
print()
vc = units['unit'].value_counts().sort_index()
print(vc.to_string())
print()
print("SHAPE_Area per unit (km2):")
print((units.groupby('unit')['SHAPE_Area'].sum()/1e6).sort_values(ascending=False).to_string())
print()
print("First feature origin (first vertex of first polygon):")
g0 = units.geometry.iloc[0]
c0 = list(g0.geoms[0].exterior.coords)[0] if g0.geom_type=="MultiPolygon" else list(g0.exterior.coords)[0]
print(f"  MTM x={c0[0]:.2f} y={c0[1]:.2f} -> lon/lat {tr.transform(c0[0],c0[1])}")
