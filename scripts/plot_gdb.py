import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

gdb = "sim3464_database/database/Geodatabase/Nili.gdb"
units = gpd.read_file(gdb, layer="GeoUnits_v1")
bnd = gpd.read_file(gdb, layer="MapBoundary")
contacts = gpd.read_file(gdb, layer="GeoContacts")
linear = gpd.read_file(gdb, layer="LinearFeatures")
surf = gpd.read_file(gdb, layer="SurfaceFeatures")
ellipse = gpd.read_file(gdb, layer="LandingEllipse")

# --- Fig 1: geologic units ---
fig, ax = plt.subplots(figsize=(10, 10))
# color by 'unit' code
uniq = sorted(units['unit'].unique())
cmap = plt.get_cmap('tab20', len(uniq))
color_map = {u: cmap(i) for i, u in enumerate(uniq)}
units['__c'] = units['unit'].map(color_map)
units.plot(ax=ax, color=units['__c'], edgecolor='black', linewidth=0.15)
bnd.boundary.plot(ax=ax, color='red', linewidth=1.2)
ellipse.boundary.plot(ax=ax, color='cyan', linewidth=1.2)
ax.set_title("SIM3464 Nili.gdb — GeoUnits_v1 (1304 polys) + MapBoundary (red) + LandingEllipse (cyan)")
ax.set_xlabel("Easting (m, MTM clon77.5E)")
ax.set_ylabel("Northing (m, MTM clon77.5E)")
ax.set_aspect('equal')
handles = [Patch(facecolor=color_map[u], edgecolor='black',
                 label=f"{u}: {units[units.unit==u].iloc[0]['symbol']} — {units[units.unit==u].iloc[0]['name']} ({(units[units.unit==u]['SHAPE_Area'].sum()/1e6):.1f} km2)")
           for u in uniq]
ax.legend(handles=handles, fontsize=7, loc='upper left', bbox_to_anchor=(1.01, 1.0))
plt.tight_layout()
plt.savefig("nili_geounits.png", dpi=150)
print("saved nili_geounits.png")

# --- Fig 2: contacts + linears + surface over units (light) ---
fig2, ax2 = plt.subplots(figsize=(10, 10))
units.plot(ax=ax2, color='lightgrey', edgecolor='none')
contacts.plot(ax=ax2, color='black', linewidth=0.4)
linear.plot(ax=ax2, color='blue', linewidth=0.5)
surf.boundary.plot(ax=ax2, color='orange', linewidth=0.4)
bnd.boundary.plot(ax=ax2, color='red', linewidth=1.2)
ellipse.boundary.plot(ax=ax2, color='cyan', linewidth=1.2)
ax2.set_title("SIM3464 — GeoContacts (black) + LinearFeatures (blue) + SurfaceFeatures (orange)")
ax2.set_xlabel("Easting (m)")
ax2.set_ylabel("Northing (m)")
ax2.set_aspect('equal')
plt.tight_layout()
plt.savefig("nili_structures.png", dpi=150)
print("saved nili_structures.png")
