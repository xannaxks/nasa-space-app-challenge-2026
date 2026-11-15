#done
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
