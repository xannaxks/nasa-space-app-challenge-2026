import numpy as np
from map_load import CELL_RES_M

def compute_obstacle_density(
    elevation: np.ndarray,
    valid: np.ndarray,
    row: int,
    col: int,
    method: str = "detrended_residual",
    neighborhood_radius: int = 1,
    detrend: bool = True,
    residual_threshold_m: float = 3.0,
    slope_threshold_deg: float = 15.0,
    tri_threshold_m: float = 4.0,
    res_m: float = CELL_RES_M,
) -> float:
    """Dispatch to one of the obstacle-density methods; returns 0..1."""
    method = _check_method("obstacle", method, _VALID_OBSTACLE_METHODS)
    neighborhood_radius = _validate_radius(neighborhood_radius)
    if not isinstance(detrend, bool):
        raise TypeError("detrend must be a bool")
    values = extract_window(elevation, valid, row, col, neighborhood_radius)
    grid, mask = extract_window_grid(elevation, valid, row, col, neighborhood_radius)
    centre = float(np.asarray(elevation, dtype=float)[int(row), int(col)])
    if method == "elevation_difference":
        return obstacle_elevation_difference(values, centre, residual_threshold_m)
    if method == "detrended_residual":
        return obstacle_detrended_residual(grid, mask, residual_threshold_m, res_m)
    if method == "local_slope":
        return obstacle_local_slope(grid, mask, slope_threshold_deg, res_m)
    if method == "tri_threshold":
        return obstacle_tri_threshold(grid, mask, tri_threshold_m)
    # multi_threshold: mean density over default severity ladder.
    densities = obstacle_multi_threshold(grid, mask, (1.5, 3.0, 6.0), res_m)
    return float(np.mean(densities))
