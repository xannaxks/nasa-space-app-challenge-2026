import io

for path in ("api.py", "routing.py"):
    with io.open(path, encoding="utf-8") as f:
        src = f.read()
    orig = src
    fixes = [
        # api.py: waypoint loop bodies mangled to 24 spaces
        (
            "        if not bool(maps.valid[_r, _c]):\n                        logger.warning(",
            "        if not bool(maps.valid[_r, _c]):\n            logger.warning(",
        ),
        # api.py: docstring stray indent
        (
            "    backtracking), and the full first-to-last path is concatenated and\n        returned for frontend rendering.",
            "    backtracking), and the full first-to-last path is concatenated and\n    returned for frontend rendering.",
        ),
        # api.py: cost_matrix over-indented
        (
            "        return float(leg_cache[(i, j)].distance[points[j]])\n\n        cost_matrix = ",
            "        return float(leg_cache[(i, j)].distance[points[j]])\n\n    cost_matrix = ",
        ),
        # api.py: leg unreachable branch
        (
            "            legs.append(TourLeg(start=start_ref, end=end_ref, reached=False))\n            warnings.append(f\"leg {a}->{b} is unreachable under this cost model\")\n            logger.warning(",
            "            legs.append(TourLeg(start=start_ref, end=end_ref, reached=False))\n            warnings.append(f\"leg {a}->{b} is unreachable under this cost model\")\n        logger.warning(",
        ),
        # api.py: leg unreachable continuation over-indented
        (
            "                           a, b, tuple(points[a]), tuple(points[b]))\n            continue",
            "                           a, b, tuple(points[a]), tuple(points[b]))\n            continue",
        ),
        # api.py: cell docstring indent
        (
            ") -> CellCostResponse:\n        \"\"\"Inspect one cell",
            ") -> CellCostResponse:\n    \"\"\"Inspect one cell",
        ),
        # api.py: map_info dict keys
        (
            "        \"shape\": [int(arr.shape[0]), int(arr.shape[1])],\n                \"min\": float(finite.min()),",
            "        \"shape\": [int(arr.shape[0]), int(arr.shape[1])],\n        \"min\": float(finite.min()),",
        ),
        # api.py: map_info duplicated return
        (
            "        \"percentiles\": {str(p): float(np.percentile(finite, p)) for p in (2, 5, 25, 50, 75, 95, 98)},\n    }\n    logger.info(\"map_info:",
            "        \"percentiles\": {str(p): float(np.percentile(finite, p)) for p in (2, 5, 25, 50, 75, 95, 98)},\n    }\n    logger.info(\"map_info:",
        ),
        # api.py: no-legs branch indent
        (
            "        full_cells.extend(cells if not full_cells else cells[1:])\n        if not full_cells:\n        logger.warning(",
            "        full_cells.extend(cells if not full_cells else cells[1:])\n    if not full_cells:\n        logger.warning(",
        ),
        # api.py: validate summary log inside loop -> move after loop
        (
            "            problems.append(f\"waypoint {idx} ({cell.row}, {cell.col}) is nodata (impassable)\")\n        logger.info(\"validate: valid=",
            "            problems.append(f\"waypoint {idx} ({cell.row}, {cell.col}) is nodata (impassable)\")\n    logger.info(\"validate: valid=",
        ),
        # routing.py: precompute except indent
        (
            "                )\n                        except ValueError:\n                obstacles[row, col] = 0.0",
            "                )\n            except ValueError:\n                obstacles[row, col] = 0.0",
        ),
        # routing.py: thermal_cost indent
        (
            "        ).reshape(height, width),\n                \"thermal_cost\": np.clip(",
            "        ).reshape(height, width),\n        \"thermal_cost\": np.clip(",
        ),
        # routing.py: dijkstra expansions indent
        (
            "        heapq.heappush(heap, (0.0, row, col, TraverseState()))\n\n        expansions = 0",
            "        heapq.heappush(heap, (0.0, row, col, TraverseState()))\n\n    expansions = 0",
        ),
        # routing.py: dijkstra alt indent
        (
            "            if step >= IMPASSABLE_COST or not math.isfinite(step):\n                continue\n                        alt = cost + step",
            "            if step >= IMPASSABLE_COST or not math.isfinite(step):\n                continue\n            alt = cost + step",
        ),
        # routing.py: reconstruct guards
        (
            "    if not math.isfinite(result.distance[row, col]):\n        raise ValueError(\"Target is unreachable\")",
            "    if not math.isfinite(result.distance[row, col]):\n        raise ValueError(\"Target is unreachable\")",
        ),
        (
            "        path.append((row, col))\n                if len(path) > guard:",
            "        path.append((row, col))\n        if len(path) > guard:",
        ),
    ]
    applied = 0
    for old, new in fixes:
        if old == new:
            continue
        if old in src:
            src = src.replace(old, new)
            applied += 1
    if src != orig:
        with io.open(path, "w", encoding="utf-8", newline="") as f:
            f.write(src)
    print(path, "fixes applied:", applied)
