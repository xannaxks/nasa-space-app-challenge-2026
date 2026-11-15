
import numpy as np
from map_load import CELL_RES_M

# ---------------------------------------------------------------------------
# 1. Roughness (8 methods, metres of local relief)
# ---------------------------------------------------------------------------


def roughness_std(values: np.ndarray, detrend: bool = False, **kwargs) -> float:
    """Standard deviation of neighbourhood elevations (fast, simple)."""
    values = np.asarray(values, dtype=float)
    if values.size < MIN_VALID_NEIGHBORS:
        raise ValueError("Not enough valid neighbours for std")
    if detrend:
        return roughness_detrended_rms(kwargs["grid"], kwargs["mask"], kwargs.get("res_m", CELL_RES_M))
    return float(np.std(values))


def roughness_mad(values: np.ndarray, around_median: bool = False, **kwargs) -> float:
    """Mean absolute deviation from the mean (or median)."""
    values = np.asarray(values, dtype=float)
    if values.size < MIN_VALID_NEIGHBORS:
        raise ValueError("Not enough valid neighbours for MAD")
    centre = float(np.median(values)) if around_median else float(np.mean(values))
    return float(np.mean(np.abs(values - centre)))


def roughness_medad(values: np.ndarray, **kwargs) -> float:
    """Median absolute deviation from the neighbourhood median (robust)."""
    values = np.asarray(values, dtype=float)
    if values.size < MIN_VALID_NEIGHBORS:
        raise ValueError("Not enough valid neighbours for MedAD")
    return float(np.median(np.abs(values - np.median(values))))


def roughness_percentile_range(
    values: np.ndarray,
    percentile_low: float = 10.0,
    percentile_high: float = 90.0,
    **kwargs,
) -> float:
    """Robust elevation spread ``P_high - P_low`` (default P90 - P10)."""
    _validate_percentiles(percentile_low, percentile_high)
    values = np.asarray(values, dtype=float)
    if values.size < MIN_VALID_NEIGHBORS:
        raise ValueError("Not enough valid neighbours for percentile range")
    return float(np.percentile(values, float(percentile_high)) - np.percentile(values, float(percentile_low)))


def roughness_tri_riley(grid: np.ndarray, mask: np.ndarray, **kwargs) -> float:
    """TRI (Riley): RMS difference centre vs neighbours. Slope-sensitive."""
    grid = np.asarray(grid, dtype=float)
    cy, cx = (np.array(grid.shape, dtype=float) - 1.0) / 2.0
    icy, icx = int(round(cy)), int(round(cx))
    centre = grid[icy, icx]
    if not np.isfinite(centre):
        raise ValueError("Centre cell is not valid")
    neighbour = grid[mask]
    neighbour = neighbour[np.isfinite(neighbour)]
    # Exclude the centre cell itself when the mask contains it.
    if neighbour.size > 1:
        diffs_all = neighbour - centre
        # Drop one zero diff (the centre) if present.
        zero = np.argmin(np.abs(diffs_all))
        if diffs_all[zero] == 0.0:
            diffs_all = np.delete(diffs_all, zero)
        neighbour = diffs_all + centre
    diffs = neighbour - centre
    if diffs.size < MIN_VALID_NEIGHBORS - 1 and diffs.size == 0:
        raise ValueError("Not enough valid neighbours for TRI")
    return float(np.sqrt(np.mean(diffs**2)))


def roughness_tri_wilson(grid: np.ndarray, mask: np.ndarray, **kwargs) -> float:
    """TRI (Wilson): mean absolute centre-vs-neighbour difference."""
    grid = np.asarray(grid, dtype=float)
    cy, cx = (np.array(grid.shape, dtype=float) - 1.0) / 2.0
    icy, icx = int(round(cy)), int(round(cx))
    centre = grid[icy, icx]
    if not np.isfinite(centre):
        raise ValueError("Centre cell is not valid")
    neighbour = grid[mask].astype(float)
    neighbour = neighbour[np.isfinite(neighbour)]
    if neighbour.size > 1:
        idx = int(np.argmin(np.abs(neighbour - centre)))
        if neighbour[idx] == centre:
            neighbour = np.delete(neighbour, idx)
    if neighbour.size == 0:
        raise ValueError("Not enough valid neighbours for TRI")
    return float(np.mean(np.abs(neighbour - centre)))


def roughness_max_deviation(values: np.ndarray, **kwargs) -> float:
    """Max absolute deviation from the centre value (noise-sensitive)."""
    values = np.asarray(values, dtype=float)
    if values.size < MIN_VALID_NEIGHBORS:
        raise ValueError("Not enough valid neighbours for max deviation")
    centre = kwargs.get("centre", float(np.median(values)))
    if not math.isfinite(float(centre)):
        raise ValueError("Centre value is not finite")
    return float(np.max(np.abs(values - float(centre))))


def roughness_detrended_rms(grid: np.ndarray, mask: np.ndarray, res_m: float = CELL_RES_M, **kwargs) -> float:
    """RMS of residuals after fitting a local plane (recommended).

    Separates true local irregularity from the regional slope, so a
    smooth hillside scores ~0 while rocky ground scores high.
    """
    grid = np.asarray(grid, dtype=float)
    mask = np.asarray(mask, dtype=bool)
    plane = fit_local_plane(grid, mask, res_m)
    residuals = grid[mask] - plane[mask]
    residuals = residuals[np.isfinite(residuals)]
    if residuals.size == 0:
        raise ValueError("No valid residuals for detrended RMS")
    return float(np.sqrt(np.mean(residuals**2)))


def compute_roughness(
    elevation: np.ndarray,
    valid: np.ndarray,
    row: int,
    col: int,
    method: str = "detrended_rms",
    neighborhood_radius: int = 1,
    percentile_low: float = 10.0,
    percentile_high: float = 90.0,
    detrend: bool = True,
    res_m: float = CELL_RES_M,
    slope_threshold_deg: float = 15.0,
    tri_threshold_m: float = 4.0,
) -> float:
    """Dispatch to one of the 8 roughness methods; returns metres >= 0."""
    method = _check_method("roughness", method, _VALID_ROUGHNESS_METHODS)
    neighborhood_radius = _validate_radius(neighborhood_radius)
    _validate_percentiles(percentile_low, percentile_high)
    if not isinstance(detrend, bool):
        raise TypeError("detrend must be a bool")
    values = extract_window(elevation, valid, row, col, neighborhood_radius)
    grid, mask = extract_window_grid(elevation, valid, row, col, neighborhood_radius)
    if method == "std":
        if detrend:
            return roughness_detrended_rms(grid, mask, res_m)
        return roughness_std(values)
    if method == "mad":
        if detrend:
            resid = grid[mask] - fit_local_plane(grid, mask, res_m)[mask]
            return roughness_mad(resid[np.isfinite(resid)])
        return roughness_mad(values)
    if method == "medad":
        if detrend:
            resid = grid[mask] - fit_local_plane(grid, mask, res_m)[mask]
            return roughness_medad(resid[np.isfinite(resid)])
        return roughness_medad(values)
    if method == "percentile_range":
        if detrend:
            resid = grid[mask] - fit_local_plane(grid, mask, res_m)[mask]
            finite = resid[np.isfinite(resid)]
            return float(np.percentile(finite, float(percentile_high)) - np.percentile(finite, float(percentile_low)))
        return roughness_percentile_range(values, percentile_low, percentile_high)
    if method == "tri_riley":
        return roughness_tri_riley(grid, mask)
    if method == "tri_wilson":
        return roughness_tri_wilson(grid, mask)
    if method == "max_deviation":
        centre = float(np.asarray(elevation, dtype=float)[int(row), int(col)])
        if not math.isfinite(centre) or detrend:
            plane = fit_local_plane(grid, mask, res_m)
            cy, cx = (np.array(grid.shape, dtype=float) - 1.0) / 2.0
            centre = float(plane[int(round(cy)), int(round(cx))])
        if detrend:
            resid = grid[mask] - fit_local_plane(grid, mask, res_m)[mask]
            return roughness_max_deviation(resid[np.isfinite(resid)], centre=0.0)
        return roughness_max_deviation(values, centre=centre)
    # detrended_rms (recommended default)
    return roughness_detrended_rms(grid, mask, res_m)