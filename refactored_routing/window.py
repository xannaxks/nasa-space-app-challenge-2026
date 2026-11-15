# Window / neighbourhood limits (a radius-4 window is 9x9 = 81 cells).
MIN_NEIGHBORHOOD_RADIUS = 1
MAX_NEIGHBORHOOD_RADIUS = 4
MIN_VALID_NEIGHBORS = 3

def extract_window(
    elevation: np.ndarray,
    valid: np.ndarray,
    row: int,
    col: int,
    neighborhood_radius: int,
) -> np.ndarray:
    """Return valid elevations in the square window around ``(row, col)``.

    The window spans ``radius`` cells in each direction, clipped to the
    raster bounds. Invalid (nodata) cells are dropped. Raises
    ``ValueError`` when no valid cell remains, ``IndexError`` when the
    centre itself is out of bounds.
    """
    if not isinstance(elevation, np.ndarray) or not isinstance(valid, np.ndarray):
        raise TypeError("elevation and valid must be numpy arrays")
    if elevation.shape != valid.shape or elevation.ndim != 2:
        raise ValueError("elevation and valid must be 2-D arrays of equal shape")
    height, width = elevation.shape
    if not (0 <= int(row) < height and 0 <= int(col) < width):
        raise IndexError("Cell is outside the raster")
    neighborhood_radius = _validate_radius(neighborhood_radius)
    row, col = int(row), int(col)
    r0, r1 = max(0, row - neighborhood_radius), min(height, row + neighborhood_radius + 1)
    c0, c1 = max(0, col - neighborhood_radius), min(width, col + neighborhood_radius + 1)
    patch = np.asarray(elevation[r0:r1, c0:c1], dtype=float).ravel()
    mask = np.asarray(valid[r0:r1, c0:c1], dtype=bool).ravel()
    values = patch[mask]
    values = values[np.isfinite(values)]
    if values.size == 0:
        raise ValueError("No valid elevation cells in neighbourhood")
    return values


def extract_window_grid(
    elevation: np.ndarray,
    valid: np.ndarray,
    row: int,
    col: int,
    neighborhood_radius: int,
) -> Tuple[np.ndarray, np.ndarray]:
    """Return ``(values, mask)`` grids for the window around a cell.

    ``values`` holds elevations with invalid cells as NaN; ``mask`` marks
    the valid cells. Needed by the spatial (detrended / TRI) methods.
    """
    neighborhood_radius = _validate_radius(neighborhood_radius)
    if not isinstance(elevation, np.ndarray) or not isinstance(valid, np.ndarray):
        raise TypeError("elevation and valid must be numpy arrays")
    if elevation.shape != valid.shape or elevation.ndim != 2:
        raise ValueError("elevation and valid must be 2-D arrays of equal shape")
    height, width = elevation.shape
    if not (0 <= int(row) < height and 0 <= int(col) < width):
        raise IndexError("Cell is outside the raster")
    row, col = int(row), int(col)
    r0, r1 = max(0, row - neighborhood_radius), min(height, row + neighborhood_radius + 1)
    c0, c1 = max(0, col - neighborhood_radius), min(width, col + neighborhood_radius + 1)
    raw = np.asarray(elevation[r0:r1, c0:c1], dtype=float)
    mask = np.asarray(valid[r0:r1, c0:c1], dtype=bool) & np.isfinite(raw)
    values = np.where(mask, raw, np.nan)
    if int(np.count_nonzero(mask)) == 0:
        raise ValueError("No valid elevation cells in neighbourhood")
    return values, mask
