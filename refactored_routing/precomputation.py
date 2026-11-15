

def precompute_cell_layers(maps: RasterMaps, config: CostConfig) -> Dict[str, np.ndarray]:
    """Precompute per-cell roughness / obstacle / geology / IR / thermal."""
    started = time.perf_counter()
    config.validate()
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
