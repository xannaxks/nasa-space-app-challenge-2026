import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell
def _(MAX_REASONABLE_PENALTY):
    def _():

        import ast
        import heapq
        import math
        import operator
        import time
        from dataclasses import dataclass, field
        from pathlib import Path
        from typing import Dict
        from typing import Callable, List, Sequence, Tuple
        from default_values import (
            asc_penalty_expr,
            desc_penalty_expr,
            flat_penalty_expr,

            continuous_asc_penalty_expr,
            continuous_desc_penalty_expr,
            continuous_flat_penalty_expr ,

            terrain_roughnes_penalty_expr,
            thermal_swing_risk_penalty_expr,
            obstacle_density_penalty_expr,
            terrain_type_IR_based_penalty_expr
        )

        import numpy as np
        EXPRESSION_MAX_LENGTH = 256
        EXPRESSION_MAX_NODES = 50
        EXPRESSION_MAX_EXPONENT = 10.0


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

    _()
    return


@app.cell
def _(ALIGNED_DIR, precompute_cell_layers):
    def _():
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
    
        # __all__ = [
        #     "ALIGNED_DIR",
        #     "CELL_RES_M",
        #     "CostConfig",
        #     "DEFAULT_CONFIG",
        #     "DEFAULT_GEOLOGY_PENALTIES",
        #     "DEFAULT_GEOLOGY_PENALTY",
        #     "DEFAULT_TERRAIN_SOURCE",
        #     "DijkstraResult",
        #     "ELEVATION_DIRECTION_THRESHOLD",
        #     "EdgeInfo",
        #     "GEOLOGY_UNIT_NAMES",
        #     "INF",
        #     "IMPASSABLE_COST",
        #     "OBSTACLE_DEFAULTS",
        #     "ROUGHNESS_DEFAULTS",
        #     "RasterMaps",
        #     "TraverseState",
        #     "W_CONTINUOUS_ELEVATION",
        #     "W_ELEVATION",
        #     "W_OBSTACLES",
        #     "W_ROUGHNESS",
        #     "W_TERRAIN_GEOLOGY",
        #     "W_TERRAIN_IR",
        #     "W_THERMAL",
        #     "asc_penalty_expr",
        #     "asc_penalty_func",
        #     "calc_cost",
        #     "compile_expression",
        #     "compute_obstacle_density",
        #     "compute_roughness",
        #     "continuous_asc_penalty_expr",
        #     "continuous_asc_penalty_func",
        #     "continuous_desc_penalty_expr",
        #     "continuous_desc_penalty_func",
        #     "continuous_flat_penalty_expr",
        #     "continuous_flat_penalty_func",
        #     "desc_penalty_expr",
        #     "desc_penalty_func",
        #     "dijkstra",
        #     "extract_window",
        #     "extract_window_grid",
        #     "fit_local_plane",
        #     "flat_penalty_expr",
        #     "flat_penalty_func",
        #     "get_continuous_elevation_cost",
        #     "get_distance",
        #     "get_edge_info",
        #     "get_elevation_cost",
        #     "get_obstacle_density_cost",
        #     "get_roughness_cost",
        #     "get_terrain_type_IR_based_cost",
        #     "get_terrain_type_geological_based_cost",
        #     "get_thermal_swing_risk_cost",
        #     "get_traverse_state",
        #     "load_maps",
        #     "obstacle_density_penalty_expr",
        #     "obstacle_density_penalty_func",
        #     "obstacle_detrended_residual",
        #     "obstacle_elevation_difference",
        #     "obstacle_local_slope",
        #     "obstacle_multi_threshold",
        #     "obstacle_tri_threshold",
        #     "path_length_m",
        #     "precompute_cell_layers",
        #     "reconstruct_path",
        #     "route",
        #     "roughness_detrended_rms",
        #     "roughness_mad",
        #     "roughness_max_deviation",
        #     "roughness_medad",
        #     "roughness_percentile_range",
        #     "roughness_std",
        #     "roughness_tri_riley",
        #     "roughness_tri_wilson",
        #     "terrain_roughnes_penalty_expr",
        #     "terrain_roughnes_penalty_func",
        #     "terrain_type_IR_based_penalty_expr",
        #     "terrain_type_IR_based_penalty_func",
        #     "terrain_type_geological_based_dict",
        #     "thermal_swing_risk_penalty_expr",
        #     "thermal_swing_risk_penalty_func",
        # ]
    
    
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
    _()
    return


@app.cell
def _():
    def _():
    
        import logging
        logger = logging.getLogger("traverse.routing")
    _()
    return


@app.cell
def _(math, time):
    def _():
    
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
    _()
    return


@app.cell
def _(
    IMPASSABLE_COST,
    INF,
    TI,
    TJ,
    TraverseState,
    calc_cost,
    heapq,
    logger,
    logging,
    math,
    time,
):
    def _():
        from dataclasses import dataclass
        import numpy as np
        from typing import Tuple, Dict, Sequence, List
        from map_load import RasterMaps, CELL_RES_M
        from cost_config import CostConfig
    
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
                if settled[row, col]:
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
    
    _()
    return


@app.cell
def _(math):
    def _():
        from dataclasses import dataclass
        from typing import Dict
        from default_values import (
            asc_penalty_expr,
            desc_penalty_expr, 
            flat_penalty_expr ,
        
            continuous_asc_penalty_expr ,
            continuous_desc_penalty_expr,
            continuous_flat_penalty_expr,
        
            terrain_roughnes_penalty_expr ,
            thermal_swing_risk_penalty_expr ,
            obstacle_density_penalty_expr,
            terrain_type_IR_based_penalty_expr ,
        
            GEOLOGY_UNIT_NAMES,
            DEFAULT_GEOLOGY_PENALTIES,
            terrain_type_geological_based_dict,
            DEFAULT_GEOLOGY_PENALTY,
            _VALID_TERRAIN_SOURCES ,
            DEFAULT_TERRAIN_SOURCE,
        
            W_ELEVATION,
            W_CONTINUOUS_ELEVATION,
            W_ROUGHNESS ,
            W_OBSTACLES ,
            W_TERRAIN_GEOLOGY ,
            W_TERRAIN_IR ,
            W_THERMAL ,
        
            ELEVATION_DIRECTION_THRESHOLD ,
        
            ROUGHNESS_DEFAULTS, 
        
            OBSTACLE_DEFAULTS ,
        )
    
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
    _()
    return


@app.cell
def _(
    MIN_VALID_NEIGHBORS,
    extract_window,
    extract_window_grid,
    fit_local_plane,
    math,
):
    def _():

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
    _()
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
