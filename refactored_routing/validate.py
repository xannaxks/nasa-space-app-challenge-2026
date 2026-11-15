
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

