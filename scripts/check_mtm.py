import rasterio
from rasterio.warp import transform

s = rasterio.open('aligned/DTM_CTX_mosaic_MTM100m_norm01.tif')
print('crs valid:', bool(s.crs))
GEO = 'GEOGCS["GCS_Mars_2000_Sphere",DATUM["Mars_2000_(Sphere)",SPHEROID["Mars_2000_Sphere",3396190,0]],PRIMEM["Reference_Meridian",0],UNIT["degree",0.0174532925199433]]'
xs = [-39528.90637077264, 16971.09362922736]
ys = [1108513.8212198, 1049113.8212198]
lon, lat = transform(s.crs, GEO, xs, ys)
print('lon:', lon)
print('lat:', lat)
