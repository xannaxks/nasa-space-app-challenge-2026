# done

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