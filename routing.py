"""Traverse-cost routing on pixel-aligned MTM 100 m rasters.

Aggregated from the traverse-cost notebook (``test.py`` / ``methods.md``)
as a regular ``.py`` module (no marimo dependency).

Layers (``aligned/``)::

    DTM_CTX_mosaic_MTM100m.tif          raw elevation, metres, nodata -9999
    DTM_CTX_mosaic_MTM100m_norm01.tif   elevation stretched 0..1 (viewing)
    DTM_slope_deg_MTM100m.tif           slope, degrees
    THEMIS_Day_MTM100m_norm01.tif       day IR 0..1
    THEMIS_Night_MTM100m_norm01.tif     night IR 0..1
    GeoUnits_MTM100m.tif                geology codes 0..14 (0 = background)

What this module provides:

1. Hardened safe-expression compiler for user-tunable penalty curves.
2. Optimal default penalty expressions (only the geology dict is empty).
3. All 8 roughness methods (default: detrended RMS) + all 5 obstacle
   density methods (default: detrended-residual threshold).
4. Hardened per-edge traverse cost (``calc_cost``) and a heap-based
   Dijkstra shortest-path search over the 8-connected grid.

Only functionality described in ``methods.md`` is implemented.
"""

from __future__ import annotations

import ast
import heapq
import json
import logging
import math
import operator
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Sequence, Tuple

import numpy as np

logger = logging.getLogger("traverse.routing")

try:
    import rasterio
except ImportError:  # pragma: no cover - optional at import time
    rasterio = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Penalty / cost values are dimensionless multipliers.
MAX_REASONABLE_PENALTY = 1.0e6
#: Traverse cost of a cell that must never be entered (nodata / void).
IMPASSABLE_COST = 1.0e9
#: Dijkstra "infinity" (float so accumulated metres + penalties fit).
INF = float("inf")

#: 8-connected neighbourhood: E, W, S, N, SE, SW, NE, NW.
TI = (0, 0, 1, -1, 1, -1, 1, -1)
TJ = (1, -1, 0, 0, 1, -1, -1, 1)
#: Per-step metres for a 100 m grid: orthogonal 100, diagonal 100*sqrt(2).
CELL_RES_M = 100.0

# Safe-expression compiler limits (unchanged semantics, hardened checks).
EXPRESSION_MAX_LENGTH = 256
EXPRESSION_MAX_NODES = 50
EXPRESSION_MAX_EXPONENT = 10.0

# Window / neighbourhood limits (a radius-4 window is 9x9 = 81 cells).
MIN_NEIGHBORHOOD_RADIUS = 1
MAX_NEIGHBORHOOD_RADIUS = 4
MIN_VALID_NEIGHBORS = 3

# ---------------------------------------------------------------------------
# Safe penalty-expression compiler
# ---------------------------------------------------------------------------

BINARY_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
}

UNARY_OPERATORS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

FUNCTIONS: Dict[str, Callable] = {
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "sqrt": math.sqrt,
    "log": math.log,
    "exp": math.exp,
    "abs": abs,
    "min": min,
    "max": max,
}


def _evaluate_node(node: ast.AST, x: float) -> float:
    """Recursively evaluate one whitelisted AST node with variable ``x``."""
    if isinstance(node, ast.Constant):
        if type(node.value) not in (int, float):
            raise ValueError("Only numeric constants allowed")
        return float(node.value)
    if isinstance(node, ast.Name):
        if node.id != "x":
            raise ValueError(f"Unknown variable: {node.id!r}")
        return float(x)
    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in BINARY_OPERATORS:
            raise ValueError("Operator not allowed")
        left = _evaluate_node(node.left, x)
        right = _evaluate_node(node.right, x)
        if not math.isfinite(left) or not math.isfinite(right):
            raise ValueError("Non-finite operand")
        if op_type is ast.Pow and abs(right) > EXPRESSION_MAX_EXPONENT:
            raise ValueError("Exponent too large")
        if op_type is ast.Div and right == 0.0:
            raise ValueError("Division by zero")
        try:
            result = BINARY_OPERATORS[op_type](left, right)
        except (ArithmeticError, ValueError) as exc:
            raise ValueError(f"Arithmetic error: {exc}") from exc
        if not math.isfinite(result):
            raise ValueError("Non-finite result")
        return float(result)
    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in UNARY_OPERATORS:
            raise ValueError("Unary operator not allowed")
        return float(UNARY_OPERATORS[op_type](_evaluate_node(node.operand, x)))
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise ValueError("Invalid function")
        name = node.func.id
        if name not in FUNCTIONS or node.keywords:
            raise ValueError("Function not allowed")
        args = [_evaluate_node(arg, x) for arg in node.args]
        try:
            result = FUNCTIONS[name](*args)
        except (ArithmeticError, ValueError, TypeError) as exc:
            raise ValueError(f"Function error: {exc}") from exc
        if not math.isfinite(result):
            raise ValueError("Non-finite result")
        return float(result)
    raise ValueError("Invalid expression")


def compile_expression(expression: str) -> Callable[[float], float]:
    """Compile a scalar penalty expression ``f(x)`` into a hardened callable.

    Only the variable ``x``, numeric constants, ``+ - * / **`` and the
    whitelisted math helpers (sin/cos/tan/sqrt/log/exp/abs/min/max) are
    allowed. The returned function rejects NaN/inf inputs, negative
    penalties and unreasonably large outputs.
    """
    if not isinstance(expression, str):
        raise TypeError("Expression must be a string")
    if not expression.strip():
        raise ValueError("Expression must not be empty")
    if len(expression) > EXPRESSION_MAX_LENGTH:
        raise ValueError("Expression too long")
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"Invalid syntax: {exc}") from exc
    if len(list(ast.walk(tree))) > EXPRESSION_MAX_NODES:
        raise ValueError("Expression too complex")
    body = tree.body

    def function(x: float) -> float:
        try:
            value = float(x)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid input: {exc}") from exc
        if not math.isfinite(value):
            raise ValueError("Non-finite input")
        result = _evaluate_node(body, value)
        if not math.isfinite(result):
            raise ValueError("Non-finite result")
        if result < 0.0:
            raise ValueError("Negative penalty")
        if result > MAX_REASONABLE_PENALTY:
            raise ValueError("Penalty unreasonably large")
        return float(result)

    return function


# ---------------------------------------------------------------------------
# Optimal default penalty expressions
# ---------------------------------------------------------------------------
# Calibrated for the aligned Nili MTM 100 m stack:
#   slope p50 ~3.2 deg, p90 ~11.4 deg, p98 ~21.4 deg, max ~36.6 deg;
#   IR day-night diff (0..1 scaled) p5..p95 ~ -0.58..+0.58, std ~0.35;
#   elevation std ~280 m over the mosaic.
#
# Slope penalties grow quadratically from a ~4 deg free-travel deadband
# (rover-class terrain) and saturate at +6 (impassable canyon walls score
# far above any plausible detour). Flat ground still pays a small linear
# rolling term. Continuous-climb penalties are convex in run distance so
# long unbroken climbs/descents cost extra per metre. Roughness/obstacle
# penalties saturate with x/(x+k) so single bad cells cannot overflow the
# path cost. Thermal/IR penalties are mild (|x| <= 1 by construction) so
# they nudge routes without dominating slope/roughness.

asc_penalty_expr = "min(6.0, 0.004 * max(0.0, x - 4.0) ** 2)"
desc_penalty_expr = "min(6.0, 0.0025 * max(0.0, x - 5.0) ** 2)"
flat_penalty_expr = "min(6.0, 0.02 * x)"

continuous_asc_penalty_expr = "0.00025 * x ** 2"
continuous_desc_penalty_expr = "0.00015 * x ** 2"
continuous_flat_penalty_expr = "0.0 * x"

terrain_roughnes_penalty_expr = "4.0 * x / (x + 3.0)"
thermal_swing_risk_penalty_expr = "1.5 * abs(x)"
obstacle_density_penalty_expr = "5.0 * x / (x + 0.35)"
terrain_type_IR_based_penalty_expr = "1.2 * abs(x)"

asc_penalty_func = compile_expression(asc_penalty_expr)
desc_penalty_func = compile_expression(desc_penalty_expr)
flat_penalty_func = compile_expression(flat_penalty_expr)

continuous_asc_penalty_func = compile_expression(continuous_asc_penalty_expr)
continuous_desc_penalty_func = compile_expression(continuous_desc_penalty_expr)
continuous_flat_penalty_func = compile_expression(continuous_flat_penalty_expr)

terrain_roughnes_penalty_func = compile_expression(terrain_roughnes_penalty_expr)
thermal_swing_risk_penalty_func = compile_expression(
    thermal_swing_risk_penalty_expr
)
obstacle_density_penalty_func = compile_expression(obstacle_density_penalty_expr)
terrain_type_IR_based_penalty_func = compile_expression(
    terrain_type_IR_based_penalty_expr
)

#: Human-readable GeoUnits names for codes 1..14 (code 0 = background).
#: Shown in API docs so users understand which unit they penalise.
GEOLOGY_UNIT_NAMES: Dict[int, str] = {
    1: "1 - Eolian bedform unit",
    2: "2 - Nili planum fan unit",
    3: "3 - Jezero fan 1 unit",
    4: "4 - Jezero fan 2 unit",
    5: "5 - Jezero floor unit",
    6: "6 - Lower etched unit",
    7: "7 - Nili planum 1 unit",
    8: "8 - Nili planum 2 unit",
    9: "9 - Rugged bright unit",
    10: "10 - Upper etched unit",
    11: "11 - Crater ejecta unit",
    12: "12 - Crater interior unit",
    13: "13 - Crater rim unit",
    14: "14 - Smooth unit",
}
#: Reasonable default per-unit penalties (dimensionless, 0..10, direct
#: lookup - no math curve). Smooth / fan / floor units are cheap;
#: eolian bedforms, rugged bright, crater rims/interiors are expensive.
DEFAULT_GEOLOGY_PENALTIES: Dict[int, float] = {
    1: 1.5,
    2: 0.5,
    3: 0.4,
    4: 0.4,
    5: 0.3,
    6: 0.8,
    7: 0.6,
    8: 0.6,
    9: 1.2,
    10: 0.9,
    11: 1.0,
    12: 1.3,
    13: 1.6,
    14: 0.2,
}
#: Per-geology-unit penalty coefficients (direct lookup, no math curve).
#: Pre-filled with ``DEFAULT_GEOLOGY_PENALTIES``; per-request overrides
#: swap this global (see api._cell_layers / post_route). Unknown codes
#: (e.g. 0 = background) fall back to ``DEFAULT_GEOLOGY_PENALTY``.
terrain_type_geological_based_dict: Dict[int, float] = dict(DEFAULT_GEOLOGY_PENALTIES)
DEFAULT_GEOLOGY_PENALTY = 0.5
#: Which map defines the "terrain type" penalty: IR day-night swing
#: (default, recommended), geological units, or both at once (allowed
#: but NOT recommended - the two signals overlap, so mixing
#: double-counts terrain texture; prefer exactly one of them).
_VALID_TERRAIN_SOURCES = ("geological_units", "ir_swing", "both")
DEFAULT_TERRAIN_SOURCE = "ir_swing"

# Dimensionless weights balancing the local penalty terms, and the
# incremental continuous-climb term. Slope dominates; obstacles and
# roughness follow; geology/IR/thermal only nudge.
W_ELEVATION = 1.0
W_CONTINUOUS_ELEVATION = 0.5
W_ROUGHNESS = 0.8
W_OBSTACLES = 1.0
W_TERRAIN_GEOLOGY = 0.6
W_TERRAIN_IR = 0.3
W_THERMAL = 0.3

#: Elevation change below this is "flat" (100 m cells, CTX DTM noise).
ELEVATION_DIRECTION_THRESHOLD = 1.0

#: Default roughness configuration: detrended RMS, 3x3 window.
ROUGHNESS_DEFAULTS = {
    "method": "detrended_rms",
    "neighborhood_radius": 1,
    "percentile_low": 10.0,
    "percentile_high": 90.0,
    "detrend": True,
    "slope_threshold_deg": 15.0,
    "tri_threshold_m": 4.0,
}

#: Default obstacle-density configuration: detrended-residual threshold.
OBSTACLE_DEFAULTS = {
    "method": "detrended_residual",
    "neighborhood_radius": 1,
    "detrend": True,
    "residual_threshold_m": 3.0,
    "slope_threshold_deg": 15.0,
    "tri_threshold_m": 4.0,
}

# ---------------------------------------------------------------------------
# Neighbourhood helpers (shared by roughness + obstacle density)
# ---------------------------------------------------------------------------

_VALID_ROUGHNESS_METHODS = (
    "std",
    "mad",
    "medad",
    "percentile_range",
    "tri_riley",
    "tri_wilson",
    "max_deviation",
    "detrended_rms",
)

_VALID_OBSTACLE_METHODS = (
    "elevation_difference",
    "detrended_residual",
    "local_slope",
    "tri_threshold",
    "multi_threshold",
)


def _validate_radius(neighborhood_radius: int) -> int:
    if isinstance(neighborhood_radius, bool) or not isinstance(
        neighborhood_radius, int
    ):
        raise TypeError("neighborhood_radius must be an int")
    if not MIN_NEIGHBORHOOD_RADIUS <= neighborhood_radius <= MAX_NEIGHBORHOOD_RADIUS:
        raise ValueError(
            f"neighborhood_radius must be in "
            f"[{MIN_NEIGHBORHOOD_RADIUS}, {MAX_NEIGHBORHOOD_RADIUS}]"
        )
    return neighborhood_radius


def _validate_percentiles(percentile_low: float, percentile_high: float) -> None:
    for name, value in (("percentile_low", percentile_low), ("percentile_high", percentile_high)):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{name} must be a number")
        if not math.isfinite(float(value)) or not 0.0 <= float(value) <= 100.0:
            raise ValueError(f"{name} must be within [0, 100]")
    if float(percentile_low) >= float(percentile_high):
        raise ValueError("percentile_low must be < percentile_high")


def _validate_threshold(name: str, value: float, low: float, high: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number")
    value = float(value)
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"{name} must be within [{low}, {high}]")
    return value


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


def _check_method(name: str, method: str, valid: Sequence[str]) -> str:
    if not isinstance(method, str):
        raise TypeError(f"{name} method must be a string")
    method = method.strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "sd": "std",
        "standard_deviation": "std",
        "mean_absolute_deviation": "mad",
        "median_absolute_deviation": "medad",
        "p90_p10": "percentile_range",
        "percentile": "percentile_range",
        "riley": "tri_riley",
        "wilson": "tri_wilson",
        "max": "max_deviation",
        "maximum": "max_deviation",
        "detrended": "detrended_rms",
        "rms": "detrended_rms",
        "elev_diff": "elevation_difference",
        "elevation": "elevation_difference",
        "residual": "detrended_residual",
        "slope": "local_slope",
        "tri": "tri_threshold",
        "multi": "multi_threshold",
    }
    method = aliases.get(method, method)
    if method not in valid:
        raise ValueError(f"Unknown {name} method: {method!r}. Valid: {list(valid)}")
    return method


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


# ---------------------------------------------------------------------------
# 2. Obstacle density (5 methods, fraction 0..1 of blocked neighbours)
# ---------------------------------------------------------------------------


def _density(count: int, total: int) -> float:
    if total <= 0:
        raise ValueError("No valid neighbours for density")
    return float(np.clip(count / total, 0.0, 1.0))


def obstacle_elevation_difference(
    values: np.ndarray, centre: float, residual_threshold_m: float, **kwargs
) -> float:
    """Fraction of neighbours differing from centre by >= threshold."""
    residual_threshold_m = _validate_threshold("residual_threshold_m", residual_threshold_m, 0.05, 100.0)
    values = np.asarray(values, dtype=float)
    if not math.isfinite(float(centre)):
        raise ValueError("Centre value is not finite")
    return _density(int(np.count_nonzero(np.abs(values - float(centre)) >= residual_threshold_m)), values.size)


def obstacle_detrended_residual(
    grid: np.ndarray, mask: np.ndarray, residual_threshold_m: float, res_m: float = CELL_RES_M, **kwargs
) -> float:
    """Fraction of neighbours whose plane residual >= threshold (recommended)."""
    residual_threshold_m = _validate_threshold("residual_threshold_m", residual_threshold_m, 0.05, 100.0)
    plane = fit_local_plane(np.asarray(grid, dtype=float), np.asarray(mask, dtype=bool), res_m)
    residuals = np.abs(np.asarray(grid, dtype=float)[np.asarray(mask, dtype=bool)] - plane[np.asarray(mask, dtype=bool)])
    residuals = residuals[np.isfinite(residuals)]
    if residuals.size == 0:
        raise ValueError("No valid neighbours for detrended-residual density")
    return _density(int(np.count_nonzero(residuals >= residual_threshold_m)), residuals.size)


def obstacle_local_slope(
    grid: np.ndarray, mask: np.ndarray, slope_threshold_deg: float, res_m: float = CELL_RES_M, **kwargs
) -> float:
    """Fraction of neighbours whose local slope >= threshold."""
    slope_threshold_deg = _validate_threshold("slope_threshold_deg", slope_threshold_deg, 0.5, 60.0)
    grid = np.asarray(grid, dtype=float)
    cy, cx = (np.array(grid.shape, dtype=float) - 1.0) / 2.0
    icy, icx = int(round(cy)), int(round(cx))
    centre = grid[icy, icx]
    if not np.isfinite(centre):
        raise ValueError("Centre cell is not valid")
    rows, cols = np.nonzero(np.asarray(mask, dtype=bool))
    dists = np.hypot((rows - cy) * res_m, (cols - cx) * res_m)
    diffs = np.abs(grid[rows, cols] - centre)
    ok = np.isfinite(diffs) & (dists > 0)
    if int(np.count_nonzero(ok)) == 0:
        raise ValueError("No valid neighbours for local-slope density")
    slopes = np.degrees(np.arctan2(diffs[ok], dists[ok]))
    return _density(int(np.count_nonzero(slopes >= slope_threshold_deg)), slopes.size)


def obstacle_tri_threshold(
    grid: np.ndarray, mask: np.ndarray, tri_threshold_m: float, use_riley: bool = True, **kwargs
) -> float:
    """1.0 when the window TRI >= threshold, else 0.0 (cell-level flag)."""
    tri_threshold_m = _validate_threshold("tri_threshold_m", tri_threshold_m, 0.05, 100.0)
    tri = roughness_tri_riley(grid, mask) if use_riley else roughness_tri_wilson(grid, mask)
    return 1.0 if tri >= tri_threshold_m else 0.0


def obstacle_multi_threshold(
    grid: np.ndarray,
    mask: np.ndarray,
    thresholds_m: Sequence[float] = (1.5, 3.0, 6.0),
    res_m: float = CELL_RES_M,
    **kwargs,
) -> List[float]:
    """Detrended-residual density at several severity thresholds."""
    if not isinstance(thresholds_m, (list, tuple, np.ndarray)):
        raise TypeError("thresholds_m must be a sequence of numbers")
    thresholds = sorted(float(_validate_threshold("threshold_m", t, 0.05, 100.0)) for t in thresholds_m)
    if not thresholds:
        raise ValueError("thresholds_m must not be empty")
    densities = []
    for threshold in thresholds:
        densities.append(obstacle_detrended_residual(grid, mask, threshold, res_m))
    return densities


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


# ---------------------------------------------------------------------------
# Raster loading + precomputation
# ---------------------------------------------------------------------------

ALIGNED_DIR = Path("aligned")
ELEVATION_FILE = "DTM_CTX_mosaic_MTM100m.tif"
DAY_IR_FILE = "THEMIS_Day_MTM100m_norm01.tif"
NIGHT_IR_FILE = "THEMIS_Night_MTM100m_norm01.tif"
GEO_FILE = "GeoUnits_MTM100m.tif"
GEOLOGY_VECTOR_FILE = "GeoUnits_vector_MTM100m.geojson"
GEOLOGY_VECTOR_SIMPLIFIED_FILE = "GeoUnits_vector_MTM100m_simplified.geojson"
GEOLOGY_VECTOR_STATS_FILE = "GeoUnits_vector_MTM100m_stats.json"


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


@dataclass
class CostConfig:
    """All tunable parameters of the traverse cost (with optimal defaults)."""

    # Cost weights.
    w_elevation: float = W_ELEVATION
    w_continuous_elevation: float = W_CONTINUOUS_ELEVATION
    w_roughness: float = W_ROUGHNESS
    w_obstacles: float = W_OBSTACLES
    w_terrain_geology: float = W_TERRAIN_GEOLOGY
    w_terrain_ir: float = W_TERRAIN_IR
    w_thermal: float = W_THERMAL
    #: Which map defines the terrain-type penalty: "ir_swing" (default,
    #: recommended), "geological_units", or "both" (allowed but NOT
    #: recommended - the signals overlap, so mixing double-counts terrain
    #: texture; the "both" weight is halved per branch to compensate).
    terrain_source: str = DEFAULT_TERRAIN_SOURCE
    #: Per-unit geology penalty coefficients for codes 1..14 (direct lookup,
    #: no math curve). ``None`` = use the global default table.
    geology_penalties: Dict[int, float] | None = None
    #: Fallback penalty for unknown codes (e.g. 0 = background).
    geology_default_penalty: float = DEFAULT_GEOLOGY_PENALTY
    elevation_direction_threshold: float = ELEVATION_DIRECTION_THRESHOLD
    # Roughness options.
    roughness_method: str = ROUGHNESS_DEFAULTS["method"]
    roughness_radius: int = ROUGHNESS_DEFAULTS["neighborhood_radius"]
    percentile_low: float = ROUGHNESS_DEFAULTS["percentile_low"]
    percentile_high: float = ROUGHNESS_DEFAULTS["percentile_high"]
    roughness_detrend: bool = ROUGHNESS_DEFAULTS["detrend"]
    # Obstacle options.
    obstacle_method: str = OBSTACLE_DEFAULTS["method"]
    obstacle_radius: int = OBSTACLE_DEFAULTS["neighborhood_radius"]
    obstacle_detrend: bool = OBSTACLE_DEFAULTS["detrend"]
    residual_threshold_m: float = OBSTACLE_DEFAULTS["residual_threshold_m"]
    slope_threshold_deg: float = OBSTACLE_DEFAULTS["slope_threshold_deg"]
    tri_threshold_m: float = OBSTACLE_DEFAULTS["tri_threshold_m"]

    def validate(self) -> "CostConfig":
        _check_method("roughness", self.roughness_method, _VALID_ROUGHNESS_METHODS)
        _check_method("obstacle", self.obstacle_method, _VALID_OBSTACLE_METHODS)
        _validate_radius(self.roughness_radius)
        _validate_radius(self.obstacle_radius)
        _validate_percentiles(self.percentile_low, self.percentile_high)
        _validate_threshold("residual_threshold_m", self.residual_threshold_m, 0.05, 100.0)
        _validate_threshold("slope_threshold_deg", self.slope_threshold_deg, 0.5, 60.0)
        _validate_threshold("tri_threshold_m", self.tri_threshold_m, 0.05, 100.0)
        # Terrain-type source + per-unit geology penalties.
        if not isinstance(self.terrain_source, str):
            raise TypeError("terrain_source must be a string")
        self.terrain_source = self.terrain_source.strip().lower().replace("-", "_").replace(" ", "_")
        if self.terrain_source not in _VALID_TERRAIN_SOURCES:
            raise ValueError(f"terrain_source must be one of {list(_VALID_TERRAIN_SOURCES)}")
        if self.geology_penalties is None:
            self.geology_penalties = dict(DEFAULT_GEOLOGY_PENALTIES)
        if not isinstance(self.geology_penalties, dict):
            raise TypeError("geology_penalties must be a dict of code -> penalty")
        checked: Dict[int, float] = {}
        for code, penalty in self.geology_penalties.items():
            try:
                key = int(code)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"invalid geology code {code!r}") from exc
            if not 1 <= key <= 14:
                raise ValueError(f"geology code out of range (must be 1..14): {code!r}")
            if isinstance(penalty, bool) or not isinstance(penalty, (int, float)):
                raise ValueError(f"geology[{key}] penalty must be a number")
            penalty = float(penalty)
            if not math.isfinite(penalty) or not 0.0 <= penalty <= 10.0:
                raise ValueError(f"geology[{key}] penalty must be within [0, 10]")
            checked[key] = penalty
        missing = [c for c in range(1, 15) if c not in checked]
        if missing:
            raise ValueError(f"geology_penalties missing codes {missing} (need all 1..14)")
        self.geology_penalties = checked
        self.geology_default_penalty = _validate_threshold(
            "geology_default_penalty", self.geology_default_penalty, 0.0, 10.0
        )
        for name in (
            "w_elevation", "w_continuous_elevation", "w_roughness", "w_obstacles",
            "w_terrain_geology", "w_terrain_ir", "w_thermal",
        ):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value < 0.0 or value > 100.0:
                raise ValueError(f"{name} must be within [0, 100]")
            setattr(self, name, value)
        self.elevation_direction_threshold = _validate_threshold(
            "elevation_direction_threshold", self.elevation_direction_threshold, 0.0, 50.0
        )
        return self


def precompute_cell_layers(maps: RasterMaps, config: CostConfig) -> Dict[str, np.ndarray]:
    """Precompute per-cell roughness / obstacle / geology / IR / thermal."""
    started = time.perf_counter()
    # config.validate()
    logger.info(
        "precompute: start grid=%dx%d roughness=%s(r=%d,detrend=%s) obstacles=%s(r=%d)",
        maps.height, maps.width,
        config.roughness_method, config.roughness_radius, config.roughness_detrend,
        config.obstacle_method, config.obstacle_radius,
    )
    height, width = maps.height, maps.width
    roughness = np.zeros((height, width), dtype=float)
    obstacles = np.zeros((height, width), dtype=float)
    for row in range(height):
        for col in range(width):
            if not maps.valid[row, col]:
                continue
            try:
                roughness[row, col] = compute_roughness(
                    maps.elevation, maps.valid, row, col,
                    method=config.roughness_method,
                    neighborhood_radius=config.roughness_radius,
                    percentile_low=config.percentile_low,
                    percentile_high=config.percentile_high,
                    detrend=config.roughness_detrend,
                    res_m=maps.res_m,
                    slope_threshold_deg=config.slope_threshold_deg,
                    tri_threshold_m=config.tri_threshold_m,
                )
            except ValueError:
                roughness[row, col] = 0.0
            try:
                obstacles[row, col] = compute_obstacle_density(
                    maps.elevation, maps.valid, row, col,
                    method=config.obstacle_method,
                    neighborhood_radius=config.obstacle_radius,
                    detrend=config.obstacle_detrend,
                    residual_threshold_m=config.residual_threshold_m,
                    slope_threshold_deg=config.slope_threshold_deg,
                    tri_threshold_m=config.tri_threshold_m,
                    res_m=maps.res_m,
                )
            except ValueError:
                obstacles[row, col] = 0.0
        if height >= 100 and (row + 1) % 100 == 0:
            logger.info("precompute: row %d/%d", row + 1, height)
    logger.info(
        "precompute: raw stats rough_mean=%.3fm rough_max=%.3fm obst_mean=%.4f obst_max=%.3f",
        float(roughness[maps.valid].mean() if np.any(maps.valid) else 0.0),
        float(roughness.max()), float(obstacles.mean()), float(obstacles.max()),
    )
    roughness = np.clip(np.nan_to_num(roughness, nan=0.0, posinf=50.0), 0.0, 50.0)
    obstacles = np.clip(np.nan_to_num(obstacles, nan=0.0), 0.0, 1.0)
    # Per-unit geology lookup from the config (direct coefficients, no math
    # curve); unknown codes (0 = background) use the default penalty.
    penalties = config.geology_penalties or dict(DEFAULT_GEOLOGY_PENALTIES)
    fallback = float(config.geology_default_penalty)
    geology = np.vectorize(
        lambda code: float(penalties.get(int(code), fallback)),
        otypes=[float],
    )(maps.geo)
    geology = np.clip(np.nan_to_num(geology, nan=fallback), 0.0, 10.0)
    ir_diff = np.clip(maps.day_ir - maps.night_ir, -1.0, 1.0)
    layers = {
        "roughness_m": roughness,
        "roughness_cost": np.clip(
            [terrain_roughnes_penalty_func(v) for v in roughness.ravel()], 0.0, 10.0
        ).reshape(height, width),
        "obstacle_density": obstacles,
        "obstacle_cost": np.clip(
            [obstacle_density_penalty_func(v) for v in obstacles.ravel()], 0.0, 10.0
        ).reshape(height, width),
        "geology_cost": geology,
        "terrain_ir_cost": np.clip(
            [terrain_type_IR_based_penalty_func(v) for v in ir_diff.ravel()], 0.0, 10.0
        ).reshape(height, width),
        "thermal_cost": np.clip(
            [thermal_swing_risk_penalty_func(abs(v)) for v in ir_diff.ravel()], 0.0, 10.0
        ).reshape(height, width),
    }
    logger.info("precompute: done in %.2fs", time.perf_counter() - started)
    return layers


# ---------------------------------------------------------------------------
# Aligned geology vector map (GeoJSON, served to the frontend)
# ---------------------------------------------------------------------------
# ``aligned/GeoUnits_vector_MTM100m.geojson`` is the aggregated GeoUnits_v1
# export: 1304 MultiPolygon features, ALL native GDB columns preserved
# (unit, name, symbol_noSub, subscript, symbol, ORIG_FID, SHAPE_Length,
# SHAPE_Area, Color_ID) plus ``_layer`` ("GeoUnits_v1") and ``_code``
# (1..14, matching GeoUnits_MTM100m.tif raster codes).
#
# NOTE: coordinates are MTM metres (same grid as the aligned rasters), NOT
# lon/lat. GeoJSON has no MTM CRS code, so the file carries no "crs"
# member -- readers must NOT assume the GeoJSON default (EPSG:4326).

#: Strict per-feature property schema of the exported vector map.
GEOLOGY_VECTOR_PROPERTIES = (
    "unit",
    "name",
    "symbol_noSub",
    "subscript",
    "symbol",
    "ORIG_FID",
    "SHAPE_Length",
    "SHAPE_Area",
    "Color_ID",
    "_layer",
    "_code",
)

#: Max GeoJSON bytes served in one response (full file = ~70 MB).
GEOLOGY_VECTOR_MAX_BYTES = 90_000_000
#: Max features per response (file holds 1304).
GEOLOGY_VECTOR_MAX_FEATURES = 5000


def _check_geology_vector_path(
    aligned_dir: str | Path, filename: str
) -> Path:
    """Resolve + validate a geology-vector file inside ``aligned_dir``."""
    if not isinstance(filename, str) or not filename.strip():
        raise TypeError("filename must be a non-empty string")
    allowed = (GEOLOGY_VECTOR_FILE, GEOLOGY_VECTOR_SIMPLIFIED_FILE)
    if filename not in allowed:
        raise ValueError(f"unknown geology vector file {filename!r}. Valid: {list(allowed)}")
    aligned = Path(aligned_dir)
    path = (aligned / filename).resolve()
    if path.parent != aligned.resolve():
        raise ValueError("path escapes the aligned directory")
    if not path.is_file():
        raise FileNotFoundError(f"geology vector map not found: {path.name}")
    if path.stat().st_size > GEOLOGY_VECTOR_MAX_BYTES:
        raise ValueError(f"geology vector map exceeds {GEOLOGY_VECTOR_MAX_BYTES} bytes")
    return path


def load_geology_vector_stats(
    aligned_dir: str | Path = ALIGNED_DIR,
) -> Dict[str, object]:
    """Read the export sidecar (counts, bounds, legend data for the UI)."""
    path = Path(aligned_dir) / GEOLOGY_VECTOR_STATS_FILE
    if not path.is_file():
        raise FileNotFoundError(f"geology vector stats not found: {path.name}")
    try:
        stats = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"cannot parse {path.name}: {exc}") from exc
    if not isinstance(stats, dict):
        raise ValueError(f"{path.name} must hold a JSON object")
    return stats


def load_geology_vector_geojson(
    aligned_dir: str | Path = ALIGNED_DIR,
    simplified: bool = True,
    code: int | None = None,
    bbox: Sequence[float] | None = None,
    limit: int | None = None,
) -> Dict[str, object]:
    """Load the aggregated geology vector map as a GeoJSON dict.

    Args:
        aligned_dir: directory holding the exported ``*.geojson`` files.
        simplified: ``True`` (default) serves the 25 m-simplified variant
            (~3.4 MB, same 1304 features/columns); ``False`` serves the
            full-resolution file (~70 MB).
        code: optional GeoUnits ``_code`` 1..14 to keep (one-unit overlay).
        bbox: optional ``(minx, miny, maxx, maxy)`` in MTM metres; keeps
            only features whose bbox intersects the window (viewport culling).
        limit: optional cap on returned features (1..5000).

    Coordinates stay MTM metres (NOT lon/lat) -- see note above.
    """
    filename = GEOLOGY_VECTOR_SIMPLIFIED_FILE if simplified else GEOLOGY_VECTOR_FILE
    path = _check_geology_vector_path(aligned_dir, filename)
    if code is not None:
        if isinstance(code, bool) or not isinstance(code, int) or not 1 <= code <= 14:
            raise ValueError("code must be an int within [1, 14]")
    if limit is not None:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= GEOLOGY_VECTOR_MAX_FEATURES:
            raise ValueError(f"limit must be within [1, {GEOLOGY_VECTOR_MAX_FEATURES}]")
    window: Tuple[float, float, float, float] | None = None
    if bbox is not None:
        try:
            window = (float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]))
        except (TypeError, ValueError, IndexError) as exc:
            raise ValueError("bbox must be (minx, miny, maxx, maxy) numbers") from exc
        if not all(math.isfinite(v) for v in window):
            raise ValueError("bbox values must be finite")
        if not (window[0] < window[2] and window[1] < window[3]):
            raise ValueError("bbox must satisfy minx<maxx and miny<maxy")
    started = time.perf_counter()
    logger.info("geology_vector: load file=%s code=%s bbox=%s limit=%s", filename, code, window, limit)
    try:
        geojson = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"cannot parse {path.name}: {exc}") from exc
    if not isinstance(geojson, dict) or geojson.get("type") != "FeatureCollection":
        raise ValueError(f"{path.name} is not a GeoJSON FeatureCollection")
    features = geojson.get("features")
    if not isinstance(features, list):
        raise ValueError(f"{path.name} has no features list")
    logger.info("geology_vector: %d features on disk", len(features))

    def _feature_bbox(feature: Dict[str, object]) -> Tuple[float, float, float, float] | None:
        try:
            coords = feature["geometry"]["coordinates"]  # type: ignore[index]
        except (KeyError, TypeError):
            return None
        xs: List[float] = []
        ys: List[float] = []
        stack: List[object] = [coords]
        while stack:
            item = stack.pop()
            if isinstance(item, (list, tuple)):
                if item and all(isinstance(v, (int, float)) for v in item):
                    if len(item) >= 2:
                        xs.append(float(item[0]))
                        ys.append(float(item[1]))
                else:
                    stack.extend(item)
        if not xs:
            return None
        return (min(xs), min(ys), max(xs), max(ys))

    kept: List[Dict[str, object]] = []
    for feature in features:
        if not isinstance(feature, dict):
            continue
        props = feature.get("properties")
        if not isinstance(props, dict):
            continue
        if code is not None and int(props.get("_code", -1)) != code:
            continue
        if window is not None:
            fb = _feature_bbox(feature)
            if fb is None or fb[2] < window[0] or fb[0] > window[2] or fb[3] < window[1] or fb[1] > window[3]:
                continue
        kept.append(feature)
        if limit is not None and len(kept) >= limit:
            break
    logger.info(
        "geology_vector: serving %d/%d features (%.1f MB on disk, %.2fs)",
        len(kept), len(features), path.stat().st_size / 1e6, time.perf_counter() - started,
    )
    return {"type": "FeatureCollection", "name": "GeoUnits_v1", "features": kept}


# ---------------------------------------------------------------------------
# Traverse state + per-edge cost (hardened port of the notebook)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TraverseState:
    """Climb/descend run carried along a path (immutable, hashable)."""

    direction: int = 0  # -1 descending, 0 flat, +1 ascending
    run_distance: float = 0.0
    run_elevation_change: float = 0.0

    def __post_init__(self) -> None:
        if self.direction not in (-1, 0, 1):
            raise ValueError("direction must be -1, 0 or +1")
        for name in ("run_distance", "run_elevation_change"):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value < 0.0 or value > 1.0e9:
                raise ValueError(f"{name} must be finite within [0, 1e9]")


@dataclass(frozen=True)
class EdgeInfo:
    """Geometry of one 8-connected step."""

    elevation_change: float  # signed dh, metres
    slope_angle: float  # absolute slope, degrees
    direction: int  # -1 / 0 / +1
    distance: float  # step length, metres

    def __post_init__(self) -> None:
        if self.direction not in (-1, 0, 1):
            raise ValueError("direction must be -1, 0 or +1")
        if not math.isfinite(self.elevation_change) or abs(self.elevation_change) > 5000:
            raise ValueError("elevation_change is not plausible")
        if not math.isfinite(self.slope_angle) or not 0.0 <= self.slope_angle <= 90.0:
            raise ValueError("slope_angle must be within [0, 90]")
        if not math.isfinite(self.distance) or self.distance <= 0.0 or self.distance > 1.0e6:
            raise ValueError("distance must be positive and finite")


def _check_cell(maps: RasterMaps, cell: Tuple[int, int], name: str) -> Tuple[int, int]:
    if not (isinstance(cell, (tuple, list)) and len(cell) == 2):
        raise TypeError(f"{name} must be a (row, col) pair")
    row, col = int(cell[0]), int(cell[1])
    if not (0 <= row < maps.height and 0 <= col < maps.width):
        raise IndexError(f"{name} is outside the raster")
    if not maps.valid[row, col]:
        raise ValueError(f"{name} is a nodata (impassable) cell")
    return row, col


def _check_state(state: TraverseState) -> TraverseState:
    if not isinstance(state, TraverseState):
        raise TypeError("previous_state must be a TraverseState")
    return state


def get_distance(maps: RasterMaps, from_cell: Tuple[int, int], to_cell: Tuple[int, int]) -> float:
    """Planar step length in metres between two adjacent cells."""
    r0, c0 = _check_cell(maps, from_cell, "from_cell")
    r1, c1 = _check_cell(maps, to_cell, "to_cell")
    dr, dc = abs(r1 - r0), abs(c1 - c0)
    if (dr, dc) not in ((0, 1), (1, 0), (1, 1)):
        raise ValueError("Cells must be 8-connected neighbours")
    if dr == 0 and dc == 0:
        raise ValueError("Adjacent cells must be distinct")
    step = math.hypot(dr * maps.res_m, dc * maps.res_m)
    if not math.isfinite(step) or step <= 0.0:
        raise ValueError("Adjacent cells must have nonzero distance")
    return float(step)


def get_edge_info(
    maps: RasterMaps,
    from_cell: Tuple[int, int],
    to_cell: Tuple[int, int],
    elevation_direction_threshold: float = ELEVATION_DIRECTION_THRESHOLD,
) -> EdgeInfo:
    """Slope, direction and length of one step (hardened)."""
    elevation_direction_threshold = _validate_threshold(
        "elevation_direction_threshold", elevation_direction_threshold, 0.0, 50.0
    )
    r0, c0 = _check_cell(maps, from_cell, "from_cell")
    r1, c1 = _check_cell(maps, to_cell, "to_cell")
    distance = get_distance(maps, (r0, c0), (r1, c1))
    dh = float(maps.elevation[r1, c1] - maps.elevation[r0, c0])
    if not math.isfinite(dh):
        raise ValueError("Elevation difference is not finite")
    slope_angle = float(np.degrees(np.arctan2(abs(dh), distance)))
    if dh > elevation_direction_threshold:
        direction = 1
    elif dh < -elevation_direction_threshold:
        direction = -1
    else:
        direction = 0
    return EdgeInfo(elevation_change=dh, slope_angle=slope_angle, direction=direction, distance=distance)


def get_traverse_state(previous_state: TraverseState, edge: EdgeInfo) -> TraverseState:
    """Extend the climb/descend run across one edge (resets on flat/turn)."""
    _check_state(previous_state)
    if not isinstance(edge, EdgeInfo):
        raise TypeError("edge must be an EdgeInfo")
    if edge.direction == 0:
        return TraverseState()
    if edge.direction == previous_state.direction:
        return TraverseState(
            direction=edge.direction,
            run_distance=previous_state.run_distance + edge.distance,
            run_elevation_change=previous_state.run_elevation_change + abs(edge.elevation_change),
        )
    return TraverseState(
        direction=edge.direction,
        run_distance=edge.distance,
        run_elevation_change=abs(edge.elevation_change),
    )


def get_elevation_cost(edge: EdgeInfo) -> float:
    """Slope penalty for one edge (ascent / descent / flat curves)."""
    if not isinstance(edge, EdgeInfo):
        raise TypeError("edge must be an EdgeInfo")
    if edge.direction == -1:
        return float(desc_penalty_func(edge.slope_angle))
    if edge.direction == 0:
        return float(flat_penalty_func(edge.slope_angle))
    return float(asc_penalty_func(edge.slope_angle))


def get_continuous_elevation_cost(previous_state: TraverseState, new_state: TraverseState) -> float:
    """Incremental surcharge for extending an unbroken climb/descent."""
    _check_state(previous_state)
    _check_state(new_state)
    if new_state.direction == -1:
        old = continuous_desc_penalty_func(previous_state.run_distance)
        new = continuous_desc_penalty_func(new_state.run_distance)
    elif new_state.direction == 1:
        old = continuous_asc_penalty_func(previous_state.run_distance)
        new = continuous_asc_penalty_func(new_state.run_distance)
    elif new_state.direction == 0:
        old = continuous_flat_penalty_func(previous_state.run_distance)
        new = continuous_flat_penalty_func(new_state.run_distance)
    else:  # pragma: no cover - dataclass already constrains this
        raise ValueError("Invalid direction")
    return float(max(0.0, new - old))


def get_roughness_cost(layers: Dict[str, np.ndarray], cell: Tuple[int, int]) -> float:
    """Precomputed roughness penalty at a cell."""
    try:
        cost = layers["roughness_cost"]
    except (KeyError, TypeError) as exc:
        raise ValueError("layers must contain 'roughness_cost'") from exc
    row, col = int(cell[0]), int(cell[1])
    if not (0 <= row < cost.shape[0] and 0 <= col < cost.shape[1]):
        raise IndexError("Cell is outside the raster")
    value = float(cost[row, col])
    if not math.isfinite(value) or value < 0.0:
        raise ValueError("Stored roughness cost is invalid")
    return value


def get_obstacle_density_cost(layers: Dict[str, np.ndarray], cell: Tuple[int, int]) -> float:
    """Precomputed obstacle-density penalty at a cell."""
    try:
        cost = layers["obstacle_cost"]
    except (KeyError, TypeError) as exc:
        raise ValueError("layers must contain 'obstacle_cost'") from exc
    row, col = int(cell[0]), int(cell[1])
    if not (0 <= row < cost.shape[0] and 0 <= col < cost.shape[1]):
        raise IndexError("Cell is outside the raster")
    value = float(cost[row, col])
    if not math.isfinite(value) or value < 0.0:
        raise ValueError("Stored obstacle cost is invalid")
    return value


def get_terrain_type_geological_based_cost(
    maps: RasterMaps,
    cell: Tuple[int, int],
    penalties: Dict[int, float] | None = None,
    default_penalty: float = DEFAULT_GEOLOGY_PENALTY,
) -> float:
    """Geology-unit penalty: direct coefficient lookup, no math curve.

    ``penalties`` maps codes 1..14 to scores; unknown codes fall back to
    ``default_penalty``. ``None`` uses the global default table.
    """
    row, col = _check_cell(maps, cell, "cell")
    table = terrain_type_geological_based_dict if penalties is None else penalties
    code = int(maps.geo[row, col])
    try:
        value = float(table.get(code, default_penalty))
    except (TypeError, ValueError) as exc:
        raise ValueError("Geology penalty lookup failed") from exc
    if not math.isfinite(value) or value < 0.0 or value > 10.0:
        raise ValueError("Geology penalty must be within [0, 10]")
    return value


def get_thermal_swing_risk_cost(maps: RasterMaps, cell: Tuple[int, int]) -> float:
    """Thermal-inertia swing penalty from the day-night IR difference."""
    row, col = _check_cell(maps, cell, "cell")
    swing = float(np.clip(maps.day_ir[row, col] - maps.night_ir[row, col], -1.0, 1.0))
    return float(thermal_swing_risk_penalty_func(abs(swing)))


def get_terrain_type_IR_based_cost(maps: RasterMaps, cell: Tuple[int, int]) -> float:
    """Surface-texture penalty from the day-night IR difference."""
    row, col = _check_cell(maps, cell, "cell")
    swing = float(np.clip(maps.day_ir[row, col] - maps.night_ir[row, col], -1.0, 1.0))
    return float(terrain_type_IR_based_penalty_func(swing))


# ---------------------------------------------------------------------------
# Aggregated traverse cost + heap Dijkstra over the 8-connected grid
# ---------------------------------------------------------------------------

def calc_cost(
    maps: RasterMaps,
    layers: Dict[str, np.ndarray],
    from_cell: Tuple[int, int],
    to_cell: Tuple[int, int],
    previous_state: TraverseState,
    config: CostConfig,
) -> Tuple[float, TraverseState]:
    """Total cost of one step plus the resulting traverse state.

    ``distance * (1 + weighted local penalties)`` keeps every metre
    priced, while the continuous-climb surcharge is incremental so long
    unbroken runs accumulate fairly.
    """
    if not isinstance(maps, RasterMaps):
        raise TypeError("maps must be a RasterMaps")
    if not isinstance(config, CostConfig):
        raise TypeError("config must be a CostConfig")
    # config.validate()
    _check_state(previous_state)
    edge = get_edge_info(maps, from_cell, to_cell, config.elevation_direction_threshold)
    new_state = get_traverse_state(previous_state, edge)

    elevation_cost = get_elevation_cost(edge)
    continuous_cost = get_continuous_elevation_cost(previous_state, new_state)

    row, col = int(to_cell[0]), int(to_cell[1])
    roughness_cost = get_roughness_cost(layers, (row, col))
    obstacle_density_cost = get_obstacle_density_cost(layers, (row, col))
    # Terrain-type penalty: chosen map source. "both" keeps both branches
    # but halves each weight so the two overlapping texture signals do not
    # double-count (still NOT recommended - prefer exactly one source).
    terrain_source = getattr(config, "terrain_source", DEFAULT_TERRAIN_SOURCE)
    if terrain_source == "geological_units":
        terrain_geology_cost = get_terrain_type_geological_based_cost(
            maps, (row, col),
            penalties=config.geology_penalties,
            default_penalty=config.geology_default_penalty,
        )
        terrain_ir_cost = 0.0
        w_geo, w_ir = config.w_terrain_geology, 0.0
    elif terrain_source == "ir_swing":
        terrain_geology_cost = 0.0
        terrain_ir_cost = get_terrain_type_IR_based_cost(maps, (row, col))
        w_geo, w_ir = 0.0, config.w_terrain_ir
    else:  # "both"
        terrain_geology_cost = get_terrain_type_geological_based_cost(
            maps, (row, col),
            penalties=config.geology_penalties,
            default_penalty=config.geology_default_penalty,
        )
        terrain_ir_cost = get_terrain_type_IR_based_cost(maps, (row, col))
        w_geo, w_ir = config.w_terrain_geology * 0.5, config.w_terrain_ir * 0.5
    thermal_swing_cost = get_thermal_swing_risk_cost(maps, (row, col))

    # for name, value in (
    #     ("elevation_cost", elevation_cost),
    #     ("continuous_cost", continuous_cost),
    #     ("roughness_cost", roughness_cost),
    #     ("obstacle_density_cost", obstacle_density_cost),
    #     ("terrain_geology_cost", terrain_geology_cost),
    #     ("terrain_ir_cost", terrain_ir_cost),
    #     ("thermal_swing_cost", thermal_swing_cost),
    # ):
    #     if not math.isfinite(float(value)) or float(value) < 0.0:
    #         raise ValueError(f"{name} must be finite and non-negative")

    local_penalties = (
        config.w_elevation * elevation_cost
        + config.w_roughness * roughness_cost
        + w_geo * terrain_geology_cost
        + w_ir * terrain_ir_cost
        + config.w_thermal * thermal_swing_cost
        + config.w_obstacles * obstacle_density_cost
    )
    if not math.isfinite(local_penalties) or local_penalties < 0.0:
        raise ValueError("Aggregated local penalty is invalid")

    base_cost = edge.distance * (1.0 + local_penalties)
    total_cost = base_cost + config.w_continuous_elevation * continuous_cost
    if not math.isfinite(total_cost) or total_cost < 0.0:
        raise ValueError("Total step cost is invalid")
    return float(total_cost), new_state


@dataclass
class DijkstraResult:
    """Outcome of a grid search: distances, parents, states, reached flag."""

    distance: np.ndarray
    parent: np.ndarray  # direction index 0..7 into (TI, TJ), -1 = source/none
    state: np.ndarray  # TraverseState per cell (object array)
    reached: bool = False
    target: Tuple[int, int] | None = None


def _neighbours(row: int, col: int, height: int, width: int):
    for direction in range(8):
        nrow, ncol = row + TI[direction], col + TJ[direction]
        if 0 <= nrow < height and 0 <= ncol < width:
            yield direction, nrow, ncol


def dijkstra(
    maps: RasterMaps,
    layers: Dict[str, np.ndarray],
    sources: Sequence[Tuple[int, int]],
    config: CostConfig,
    target: Tuple[int, int] | None = None,
    max_expansions: int | None = None,
) -> DijkstraResult:
    """Heap-based Dijkstra from ``sources`` over valid 8-connected cells.

    ``TraverseState`` is path-dependent (unbroken climb length), so the
    stored per-cell state is the one from the cheapest arrival; the heap
    carries the running state along each candidate path. ``max_expansions``
    caps the number of settled cells for huge grids.
    """
    if not isinstance(maps, RasterMaps):
        raise TypeError("maps must be a RasterMaps")
    if not isinstance(config, CostConfig):
        raise TypeError("config must be a CostConfig")
    config.validate()
    if not sources:
        raise ValueError("At least one source cell is required")
    clean_sources = []
    for cell in sources:
        clean_sources.append(_check_cell(maps, cell, "source"))
    if target is not None:
        target = _check_cell(maps, target, "target")
    if max_expansions is not None:
        if isinstance(max_expansions, bool) or not isinstance(max_expansions, int) or max_expansions <= 0:
            raise ValueError("max_expansions must be a positive int")

    height, width = maps.height, maps.width
    n_sources = len(clean_sources)
    logger.info(
        "dijkstra: start sources=%d target=%s max_expansions=%s grid=%dx%d",
        n_sources, target, max_expansions, height, width,
    )
    started = time.perf_counter()
    distance = np.full((height, width), INF, dtype=float)
    parent = np.full((height, width), -1, dtype=np.int8)
    state = np.empty((height, width), dtype=object)
    state[:, :] = TraverseState()
    settled = np.zeros((height, width), dtype=bool)

    heap: List[Tuple[float, int, int, TraverseState]] = []
    for row, col in clean_sources:
        distance[row, col] = 0.0
        heapq.heappush(heap, (0.0, row, col, TraverseState()))

    expansions = 0
    reached = target is None
    vertex_trace = logger.isEnabledFor(logging.DEBUG)
    while heap:
        cost, row, col, path_state = heapq.heappop(heap)
        if settled[row, col] or cost != distance[row, col]:
            continue

        settled[row, col] = True
        state[row, col] = path_state
        expansions += 1

        if vertex_trace:
            logger.debug("dijkstra: settle #%d cell=(%d,%d) cost=%.2f dir=%d run=%.0fm heap=%d",
                         expansions, row, col, cost, path_state.direction,
                         path_state.run_distance, len(heap))
        elif expansions == 1 or expansions % 50000 == 0:
            logger.info("dijkstra: settled=%d heap=%d current=(%d,%d) cost=%.1f",
                        expansions, len(heap), row, col, cost)

        if target is not None and (row, col) == target:
            reached = True
            logger.info("dijkstra: target %s reached cost=%.2f after %d expansions (%.2fs)",
                        target, cost, expansions, time.perf_counter() - started)
            break
        if max_expansions is not None and expansions >= max_expansions:
            break
        for direction, nrow, ncol in _neighbours(row, col, height, width):
            if settled[nrow, ncol] or not maps.valid[nrow, ncol]:
                continue
            try:
                step, new_state = calc_cost(
                    maps, layers, (row, col), (nrow, ncol), path_state, config
                )
            except ValueError:
                continue  # impassable / degenerate step: skip neighbour
            if step >= IMPASSABLE_COST or not math.isfinite(step):
                continue
            alt = cost + step
            if alt < distance[nrow, ncol]:
                distance[nrow, ncol] = alt
                parent[nrow, ncol] = direction
                heapq.heappush(heap, (alt, nrow, ncol, new_state))
    logger.info("dijkstra: done settled=%d reached=%s target=%s elapsed=%.2fs",
                expansions, reached, target, time.perf_counter() - started)
    return DijkstraResult(distance=distance, parent=parent, state=state, reached=reached, target=target)


def reconstruct_path(result: DijkstraResult, target: Tuple[int, int]) -> List[Tuple[int, int]]:
    """Follow ``parent`` pointers from ``target`` back to its source."""
    if not isinstance(result, DijkstraResult):
        raise TypeError("result must be a DijkstraResult")
    height, width = result.distance.shape
    row, col = int(target[0]), int(target[1])
    if not (0 <= row < height and 0 <= col < width):
        raise IndexError("Target is outside the raster")
    if not math.isfinite(result.distance[row, col]):
        raise ValueError("Target is unreachable")
    logger.info("reconstruct: start target=(%d,%d) cost=%.2f", row, col, float(result.distance[row, col]))
    # Step index d means: current cell was reached FROM (row - TI[d], col - TJ[d]).
    path = [(row, col)]
    guard = height * width + 1
    while result.parent[row, col] != -1:
        direction = int(result.parent[row, col])
        if not 0 <= direction < 8:
            raise ValueError("Corrupt parent pointer")
        row, col = row - TI[direction], col - TJ[direction]
        if not (0 <= row < height and 0 <= col < width):
            raise ValueError("Parent chain leaves the raster")
        path.append((row, col))
        if len(path) > guard:
            raise ValueError("Parent chain contains a cycle")
    path.reverse()
    logger.info("reconstruct: done %d cells from (%d,%d) to (%d,%d)",
                len(path), path[0][0], path[0][1], path[-1][0], path[-1][1])
    return path


def path_length_m(path: Sequence[Tuple[int, int]], res_m: float = CELL_RES_M) -> float:
    """Planar length of a cell path in metres."""
    if float(res_m) <= 0 or not math.isfinite(float(res_m)):
        raise ValueError("res_m must be positive and finite")
    if len(path) < 2:
        return 0.0
    total = 0.0
    for (r0, c0), (r1, c1) in zip(path[:-1], path[1:]):
        dr, dc = abs(int(r1) - int(r0)), abs(int(c1) - int(c0))
        if (dr, dc) not in ((0, 1), (1, 0), (1, 1)):
            raise ValueError("Path cells must be 8-connected neighbours")
        total += math.hypot(dr * float(res_m), dc * float(res_m))
    return float(total)


# ---------------------------------------------------------------------------
# Convenience entry point (load -> precompute -> route)
# ---------------------------------------------------------------------------

def route(
    sources: Sequence[Tuple[int, int]],
    target: Tuple[int, int],
    config: CostConfig | None = None,
    aligned_dir: str | Path = ALIGNED_DIR,
    maps: RasterMaps | None = None,
    layers: Dict[str, np.ndarray] | None = None,
) -> Tuple[List[Tuple[int, int]], DijkstraResult]:
    """Load maps, precompute costs and return ``(path, result)``."""
    config = (config or CostConfig()).validate()
    maps = maps if maps is not None else load_maps(aligned_dir)
    layers = layers if layers is not None else precompute_cell_layers(maps, config)
    result = dijkstra(maps, layers, sources, config, target=target)
    if not result.reached or not math.isfinite(result.distance[target[0], target[1]]):
        raise ValueError("Target is unreachable under this cost model")
    return reconstruct_path(result, target), result


DEFAULT_CONFIG = CostConfig()

__all__ = [
    "ALIGNED_DIR",
    "CELL_RES_M",
    "CostConfig",
    "DEFAULT_CONFIG",
    "DEFAULT_GEOLOGY_PENALTIES",
    "DEFAULT_GEOLOGY_PENALTY",
    "DEFAULT_TERRAIN_SOURCE",
    "DijkstraResult",
    "ELEVATION_DIRECTION_THRESHOLD",
    "EdgeInfo",
    "GEOLOGY_UNIT_NAMES",
    "GEOLOGY_VECTOR_SIMPLIFIED_FILE",
    "GEOLOGY_VECTOR_STATS_FILE",
    "GEOLOGY_VECTOR_FILE",
    "GEOLOGY_VECTOR_MAX_BYTES",
    "GEOLOGY_VECTOR_MAX_FEATURES",
    "GEOLOGY_VECTOR_PROPERTIES",
    "INF",
    "IMPASSABLE_COST",
    "load_geology_vector_geojson",
    "load_geology_vector_stats",
    "OBSTACLE_DEFAULTS",
    "ROUGHNESS_DEFAULTS",
    "RasterMaps",
    "TraverseState",
    "W_CONTINUOUS_ELEVATION",
    "W_ELEVATION",
    "W_OBSTACLES",
    "W_ROUGHNESS",
    "W_TERRAIN_GEOLOGY",
    "W_TERRAIN_IR",
    "W_THERMAL",
    "asc_penalty_expr",
    "asc_penalty_func",
    "calc_cost",
    "compile_expression",
    "compute_obstacle_density",
    "compute_roughness",
    "continuous_asc_penalty_expr",
    "continuous_asc_penalty_func",
    "continuous_desc_penalty_expr",
    "continuous_desc_penalty_func",
    "continuous_flat_penalty_expr",
    "continuous_flat_penalty_func",
    "desc_penalty_expr",
    "desc_penalty_func",
    "dijkstra",
    "extract_window",
    "extract_window_grid",
    "fit_local_plane",
    "flat_penalty_expr",
    "flat_penalty_func",
    "get_continuous_elevation_cost",
    "get_distance",
    "get_edge_info",
    "get_elevation_cost",
    "get_obstacle_density_cost",
    "get_roughness_cost",
    "get_terrain_type_IR_based_cost",
    "get_terrain_type_geological_based_cost",
    "get_thermal_swing_risk_cost",
    "get_traverse_state",
    "load_maps",
    "obstacle_density_penalty_expr",
    "obstacle_density_penalty_func",
    "obstacle_detrended_residual",
    "obstacle_elevation_difference",
    "obstacle_local_slope",
    "obstacle_multi_threshold",
    "obstacle_tri_threshold",
    "path_length_m",
    "precompute_cell_layers",
    "reconstruct_path",
    "route",
    "roughness_detrended_rms",
    "roughness_mad",
    "roughness_max_deviation",
    "roughness_medad",
    "roughness_percentile_range",
    "roughness_std",
    "roughness_tri_riley",
    "roughness_tri_wilson",
    "terrain_roughnes_penalty_expr",
    "terrain_roughnes_penalty_func",
    "terrain_type_IR_based_penalty_expr",
    "terrain_type_IR_based_penalty_func",
    "terrain_type_geological_based_dict",
    "thermal_swing_risk_penalty_expr",
    "thermal_swing_risk_penalty_func",
]


if __name__ == "__main__":  # smoke test: compile penalties + tiny synthetic grid
    for _expr, _func in (
        (asc_penalty_expr, asc_penalty_func),
        (desc_penalty_expr, desc_penalty_func),
        (flat_penalty_expr, flat_penalty_expr and flat_penalty_func),
        (continuous_asc_penalty_expr, continuous_asc_penalty_func),
        (continuous_desc_penalty_expr, continuous_desc_penalty_func),
        (terrain_roughnes_penalty_expr, terrain_roughnes_penalty_func),
        (thermal_swing_risk_penalty_expr, thermal_swing_risk_penalty_func),
        (obstacle_density_penalty_expr, obstacle_density_penalty_func),
        (terrain_type_IR_based_penalty_expr, terrain_type_IR_based_penalty_func),
    ):
        assert _func(0.0) >= 0.0, _expr
    _elev = np.array(
        [[-2262.0, -2261.0, -2260.0], [-2262.0, -2258.0, -2260.0], [-2263.0, -2261.0, -2259.0]]
    )
    _valid = np.ones_like(_elev, dtype=bool)
    assert compute_roughness(_elev, _valid, 1, 1) >= 0.0
    assert 0.0 <= compute_obstacle_density(_elev, _valid, 1, 1) <= 1.0
    print("routing.py smoke test OK")