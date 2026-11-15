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
    config.validate()
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

    for name, value in (
        ("elevation_cost", elevation_cost),
        ("continuous_cost", continuous_cost),
        ("roughness_cost", roughness_cost),
        ("obstacle_density_cost", obstacle_density_cost),
        ("terrain_geology_cost", terrain_geology_cost),
        ("terrain_ir_cost", terrain_ir_cost),
        ("thermal_swing_cost", thermal_swing_cost),
    ):
        if not math.isfinite(float(value)) or float(value) < 0.0:
            raise ValueError(f"{name} must be finite and non-negative")

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

