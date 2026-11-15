
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

