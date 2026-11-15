#done
# ---------------------------------------------------------------------------
# Raster loading 
# ---------------------------------------------------------------------------
from logger import logger
from typing import Tuple
import numpy as np
import rasterio
from dataclasses import dataclass
from pathlib import Path

CELL_RES_M = 100.0
ALIGNED_DIR = Path("aligned")
ELEVATION_FILE = "DTM_CTX_mosaic_MTM100m.tif"
DAY_IR_FILE = "THEMIS_Day_MTM100m_norm01.tif"
NIGHT_IR_FILE = "THEMIS_Night_MTM100m_norm01.tif"
GEO_FILE = "GeoUnits_MTM100m.tif"


@dataclass
class RasterMaps:
    """In-memory, equally shaped analysis grids."""

    elevation: np.ndarray  # metres, NaN where void
    valid: np.ndarray  # bool mask of traversable cells
    day_ir: np.ndarray  # 0..1
    night_ir: np.ndarray  # 0..1
    geo: np.ndarray  # int codes 0..14
    res_m: float = CELL_RES_M
    height: int = 0
    width: int = 0

    def __post_init__(self) -> None:
        self.height, self.width = self.elevation.shape


def _read_band(path: Path, band: int = 1) -> Tuple[np.ndarray, float, object]:
    if rasterio is None:  # pragma: no cover
        raise ImportError("rasterio is required to load aligned rasters")
    with rasterio.open(path) as src:
        arr = src.read(band).astype(float)
        nodata = src.nodata
        res = float(src.res[0]) if src.res and src.res[0] else CELL_RES_M
    return arr, (float(nodata) if nodata is not None else math.nan), res


def load_maps(aligned_dir: str | Path = ALIGNED_DIR) -> RasterMaps:
    """Load and harden the four analysis rasters onto one common grid."""
    started = time.perf_counter()
    aligned = Path(aligned_dir)
    logger.info("load_maps: start dir=%s", aligned)
    elev, elev_nodata, res_m = _read_band(aligned / ELEVATION_FILE)
    logger.info("load_maps: elevation %s res=%.1fm nodata=%s", elev.shape, res_m, elev_nodata)
    day, _, _ = _read_band(aligned / DAY_IR_FILE)
    logger.info("load_maps: day IR %s", day.shape)
    night, _, _ = _read_band(aligned / NIGHT_IR_FILE)
    logger.info("load_maps: night IR %s", night.shape)
    geo_raw, _, _ = _read_band(aligned / GEO_FILE)
    logger.info("load_maps: geology %s", geo_raw.shape)
    if not (elev.shape == day.shape == night.shape == geo_raw.shape):
        raise ValueError("Aligned rasters must share one grid shape")
    valid = np.isfinite(elev)
    if math.isfinite(elev_nodata):
        valid &= elev != elev_nodata
    n_valid = int(np.count_nonzero(valid))
    logger.info("load_maps: valid cells %d/%d (%.1f%%)", n_valid, valid.size, 100.0 * n_valid / valid.size)
    elevation = np.where(valid, elev, np.nan)
    day_ir = np.clip(np.where(np.isfinite(day), day, 0.0), 0.0, 1.0)
    night_ir = np.clip(np.where(np.isfinite(night), night, 0.0), 0.0, 1.0)
    geo = np.where(np.isfinite(geo_raw), np.rint(geo_raw), 0).astype(int)
    geo = np.clip(geo, 0, 99)
    if n_valid == 0:
        raise ValueError("Elevation raster has no valid cells")
    maps = RasterMaps(elevation=elevation, valid=valid, day_ir=day_ir, night_ir=night_ir, geo=geo, res_m=res_m)
    logger.info("load_maps: done grid=%dx%d in %.2fs", maps.height, maps.width, time.perf_counter() - started)
    return maps