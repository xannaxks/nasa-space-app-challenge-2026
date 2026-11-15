
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

