import matplotlib.pyplot as plt
import tifffile
import numpy as np

files = [
 ("Caltech CTX mosaic 5m",
  "sim3464_database/sim3464_JezeroNili_FINAL/Rasters/Caltech_CTX_mosaic_feb2018/Nili_CTX_Mosaic_Beta01_Feb2018_MTM.tif"),
 ("HRSC DTM 75m (h0988 clip)",
  "sim3464_database/sim3464_JezeroNili_FINAL/Rasters/HRSC/nili_h0988_0000_da4_clip.tif"),
 ("HRSC hillshade 75m",
  "sim3464_database/sim3464_JezeroNili_FINAL/Rasters/HRSC/nili_h0988_0000_hillshade_clip.tif"),
 ("USGS CTX DTM 20m J03 pair",
  "sim3464_database/sim3464_JezeroNili_FINAL/Rasters/USGS_CTX_Stereo_DTMs/J03_045994_1986_J03_046060_1986_20m_DTM.tif"),
 ("USGS CTX ORTHO 6m J03",
  "sim3464_database/sim3464_JezeroNili_FINAL/Rasters/USGS_CTX_Stereo_DTMs/J03_045994_1986_XN_18N282W_6m_ORTHO.tif"),
 ("THEMIS DayIR 100m",
  "sim3464_database/sim3464_JezeroNili_FINAL/Rasters/USGS_THEMIS_IR_controlled_mosaic_oct2018/nili_THEMIS_DayIR_Controlled_oct2018.tif"),
 ("THEMIS NightIR 100m",
  "sim3464_database/sim3464_JezeroNili_FINAL/Rasters/USGS_THEMIS_IR_controlled_mosaic_oct2018/nili_THEMIS_NightIR_Controlled_oct2018.tif"),
]

fig, axes = plt.subplots(2, 4, figsize=(18, 10))
axes = axes.ravel()
for ax, (title, f) in zip(axes, files):
    a = tifffile.imread(f)
    vmin, vmax = np.percentile(a, (2, 98))
    ax.imshow(a, cmap='gray' if a.ndim==2 and 'IR' not in title and 'DTM' not in title and 'da4' not in title else ('terrain' if 'DTM'in title or 'da4' in title else 'gray'),
              vmin=vmin, vmax=vmax)
    ax.set_title(f"{title}\n{a.shape} {a.dtype}", fontsize=9)
    ax.set_xticks([]); ax.set_yticks([])
axes[-1].axis('off')
plt.suptitle("SIM3464 Rasters/ preview (direct read, % clipped)")
plt.tight_layout()
plt.savefig("sim3464_rasters_preview.png", dpi=130)
print("saved sim3464_rasters_preview.png")
