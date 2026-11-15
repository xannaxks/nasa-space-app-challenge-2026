
def fit_local_plane(values: np.ndarray, mask: np.ndarray, res_m: float) -> np.ndarray:
    """Least-squares plane ``z = a*x + b*y + c`` over valid window cells.

    Coordinates are in metres relative to the window centre. Falls back
    to the window mean (a flat plane) when fewer than 3 valid cells or
    the normal equations are singular.
    """
    if not isinstance(res_m, (int, float)) or not math.isfinite(float(res_m)) or float(res_m) <= 0:
        raise ValueError("res_m must be a positive finite number")
    res_m = float(res_m)
    rows, cols = np.nonzero(mask)
    z = np.asarray(values[mask], dtype=float)
    z = z[np.isfinite(z)]
    if z.size == 0:
        raise ValueError("No valid cells for plane fit")
    if z.size < MIN_VALID_NEIGHBORS:
        return np.full(values.shape, float(np.mean(z)), dtype=float)
    # Re-align coordinates with the finite subset (masks agree unless NaN).
    rows = rows[: z.size]
    cols = cols[: z.size]
    cy, cx = (np.array(values.shape, dtype=float) - 1.0) / 2.0
    design = np.column_stack(
        ((cols - cx) * res_m, (rows - cy) * res_m, np.ones(z.shape, dtype=float))
    )
    try:
        coef, _, _, _ = np.linalg.lstsq(design, z, rcond=None)
    except np.linalg.LinAlgError:
        return np.full(values.shape, float(np.mean(z)), dtype=float)
    if not np.all(np.isfinite(coef)):
        return np.full(values.shape, float(np.mean(z)), dtype=float)
    yy, xx = np.mgrid[0 : values.shape[0], 0 : values.shape[1]]
    return (coef[0] * (xx - cx) * res_m + coef[1] * (yy - cy) * res_m + coef[2]).astype(float)

