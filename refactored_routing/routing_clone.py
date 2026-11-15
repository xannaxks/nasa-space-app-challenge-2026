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
import math
import operator
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Sequence, Tuple
from map_load import RasterMaps, load_maps
from cost_config import CostConfig
from dijkstra import DijkstraResult, dijkstra, reconstruct_path
from expression_compiler import(
    asc_penalty_func,
    desc_penalty_func,
    flat_penalty_func,

    continuous_asc_penalty_func,
    continuous_desc_penalty_func,
    continuous_flat_penalty_func,

    terrain_roughnes_penalty_func, 
    thermal_swing_risk_penalty_func,
    obstacle_density_penalty_func,
    terrain_type_IR_based_penalty_func
)
from logger import logger
from default_values import(
    asc_penalty_expr,
    desc_penalty_expr,
    flat_penalty_expr,

    continuous_asc_penalty_expr,
    continuous_desc_penalty_expr,
    continuous_flat_penalty_expr,

    terrain_roughnes_penalty_expr, 
    thermal_swing_risk_penalty_expr,
    obstacle_density_penalty_expr,
    terrain_type_IR_based_penalty_expr
)
from roughness import compute_roughness
from obstacle_density import compute_obstacle_density

import numpy as np


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


# Safe-expression compiler limits (unchanged semantics, hardened checks).


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
    "INF",
    "IMPASSABLE_COST",
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