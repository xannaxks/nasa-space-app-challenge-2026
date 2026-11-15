
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

