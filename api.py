"""FastAPI + Pydantic v2 service over :mod:`routing`.

Receives every tunable traverse-cost parameter, parses/validates it with
Pydantic, runs the hardened :mod:`routing` pipeline and serialises the
result as JSON. Run with ``uvicorn api:app --reload``.
"""

from __future__ import annotations

import hashlib
import json
import math
import threading
from contextlib import contextmanager
from enum import Enum
from typing import Dict, Iterator, List, Optional

import numpy as np
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

import routing as R

class RoughnessMethod(str, Enum):
    """All 8 roughness methods from methods.md section 1."""

    std = "std"
    mad = "mad"
    medad = "medad"
    percentile_range = "percentile_range"
    tri_riley = "tri_riley"
    tri_wilson = "tri_wilson"
    max_deviation = "max_deviation"
    detrended_rms = "detrended_rms"


class ObstacleMethod(str, Enum):
    """All 5 obstacle-density methods from methods.md section 2."""

    elevation_difference = "elevation_difference"
    detrended_residual = "detrended_residual"
    local_slope = "local_slope"
    tri_threshold = "tri_threshold"
    multi_threshold = "multi_threshold"


def _finite_nonneg(name: str, value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    if not lo <= value <= hi:
        raise ValueError(f"{name} must be within [{lo}, {hi}]")
    return value


class WeightsModel(BaseModel):
    """Dimensionless cost weights (methods.md: local penalties + continuity)."""

    model_config = ConfigDict(extra="forbid")

    w_elevation: float = Field(default=R.W_ELEVATION, ge=0.0, le=100.0)
    w_continuous_elevation: float = Field(default=R.W_CONTINUOUS_ELEVATION, ge=0.0, le=100.0)
    w_roughness: float = Field(default=R.W_ROUGHNESS, ge=0.0, le=100.0)
    w_obstacles: float = Field(default=R.W_OBSTACLES, ge=0.0, le=100.0)
    w_terrain_geology: float = Field(default=R.W_TERRAIN_GEOLOGY, ge=0.0, le=100.0)
    w_terrain_ir: float = Field(default=R.W_TERRAIN_IR, ge=0.0, le=100.0)
    w_thermal: float = Field(default=R.W_THERMAL, ge=0.0, le=100.0)

    @field_validator("*")
    @classmethod
    def _finite(cls, v: float) -> float:
        if not math.isfinite(float(v)):
            raise ValueError("must be finite")
        return float(v)


class RoughnessParams(BaseModel):
    """methods.md section 3, roughness column."""

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    method: RoughnessMethod = RoughnessMethod.detrended_rms
    neighborhood_radius: int = Field(
        default=R.ROUGHNESS_DEFAULTS["neighborhood_radius"],
        ge=R.MIN_NEIGHBORHOOD_RADIUS, le=R.MAX_NEIGHBORHOOD_RADIUS,
    )
    percentile_low: float = Field(default=R.ROUGHNESS_DEFAULTS["percentile_low"], ge=0.0, le=100.0)
    percentile_high: float = Field(default=R.ROUGHNESS_DEFAULTS["percentile_high"], ge=0.0, le=100.0)
    detrend: bool = R.ROUGHNESS_DEFAULTS["detrend"]
    # Optional extras shared with obstacle config.
    slope_threshold_deg: float = Field(default=15.0, ge=0.5, le=60.0)
    tri_threshold_m: float = Field(default=4.0, ge=0.05, le=100.0)

    @model_validator(mode="after")
    def _check_percentiles(self) -> "RoughnessParams":
        if not math.isfinite(self.percentile_low) or not math.isfinite(self.percentile_high):
            raise ValueError("percentiles must be finite")
        if self.percentile_low >= self.percentile_high:
            raise ValueError("percentile_low must be < percentile_high")
        return self


class ObstacleParams(BaseModel):
    """methods.md section 3, obstacle-density column."""

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    method: ObstacleMethod = ObstacleMethod.detrended_residual
    neighborhood_radius: int = Field(
        default=R.OBSTACLE_DEFAULTS["neighborhood_radius"],
        ge=R.MIN_NEIGHBORHOOD_RADIUS, le=R.MAX_NEIGHBORHOOD_RADIUS,
    )
    detrend: bool = R.OBSTACLE_DEFAULTS["detrend"]
    residual_threshold_m: float = Field(default=R.OBSTACLE_DEFAULTS["residual_threshold_m"], ge=0.05, le=100.0)
    slope_threshold_deg: float = Field(default=R.OBSTACLE_DEFAULTS["slope_threshold_deg"], ge=0.5, le=60.0)
    tri_threshold_m: float = Field(default=R.OBSTACLE_DEFAULTS["tri_threshold_m"], ge=0.05, le=100.0)
    # Severity ladder for the multi-threshold method only.
    multi_thresholds_m: Optional[List[float]] = Field(default=None, min_length=1, max_length=8)

    @field_validator("multi_thresholds_m")
    @classmethod
    def _check_ladder(cls, v: Optional[List[float]]) -> Optional[List[float]]:
        if v is None:
            return v
        return [_finite_nonneg("threshold_m", t, 0.05, 100.0) for t in v]

    @model_validator(mode="after")
    def _check_method_needs(self) -> "ObstacleParams":
        if self.method == ObstacleMethod.multi_threshold and not self.multi_thresholds_m:
            # Falls back to routing's default (1.5, 3.0, 6.0) ladder.
            self.multi_thresholds_m = [1.5, 3.0, 6.0]
        return self

class PenaltyExpressions(BaseModel):
    """Custom ``f(x)`` curves for the 10 compiled penalty functions.

    Every field accepts either a safe expression string (same whitelist as
    ``routing.compile_expression``) or a non-negative number, which is
    treated as a constant penalty. ``null`` keeps the optimal default.
    """

    model_config = ConfigDict(extra="forbid")

    asc_penalty: Optional[str | float] = None
    desc_penalty: Optional[str | float] = None
    flat_penalty: Optional[str | float] = None
    continuous_asc_penalty: Optional[str | float] = None
    continuous_desc_penalty: Optional[str | float] = None
    continuous_flat_penalty: Optional[str | float] = None
    terrain_roughness_penalty: Optional[str | float] = None
    thermal_swing_risk_penalty: Optional[str | float] = None
    obstacle_density_penalty: Optional[str | float] = None
    terrain_type_ir_based_penalty: Optional[str | float] = None

    @field_validator("*")
    @classmethod
    def _check_expr(cls, v: Optional[str | float]) -> Optional[str | float]:
        if v is None:
            return v
        if isinstance(v, bool):
            raise ValueError("must be a string expression or a number")
        if isinstance(v, (int, float)):
            return _finite_nonneg("penalty", v, 0.0, 1.0e6)
        if not isinstance(v, str) or not v.strip():
            raise ValueError("must be a non-empty expression or a number")
        if len(v) > R.EXPRESSION_MAX_LENGTH:
            raise ValueError(f"expression longer than {R.EXPRESSION_MAX_LENGTH} chars")
        try:
            fn = R.compile_expression(v)
            fn(0.0)  # trial evaluation: rejects bad curves at parse time
        except (ValueError, TypeError) as exc:
            raise ValueError(f"invalid penalty expression: {exc}") from exc
        return v


class GeologyPenalties(BaseModel):
    """Per-unit geology multipliers keyed by GeoUnits code ``'1'..'14'``."""

    model_config = ConfigDict(extra="forbid")

    penalties: Dict[str, float] = Field(default_factory=dict)
    default_penalty: float = Field(default=R.DEFAULT_GEOLOGY_PENALTY, ge=0.0, le=10.0)

    @field_validator("penalties")
    @classmethod
    def _check_codes(cls, v: Dict[str, float]) -> Dict[str, float]:
        if len(v) > 64:
            raise ValueError("at most 64 geology codes")
        for code, penalty in v.items():
            try:
                key = int(str(code).strip())
            except (TypeError, ValueError) as exc:
                raise ValueError(f"invalid geology code {code!r}") from exc
            if not 0 <= key <= 999:
                raise ValueError(f"geology code out of range: {code!r}")
            _finite_nonneg(f"geology[{code}]", penalty, 0.0, 10.0)
        return {str(int(str(k).strip())): float(p) for k, p in v.items()}


class CellRef(BaseModel):
    """One grid cell; validated against the map inside the endpoint."""

    model_config = ConfigDict(extra="forbid")

    row: int = Field(ge=0)
    col: int = Field(ge=0)

    def as_tuple(self) -> tuple[int, int]:
        return (int(self.row), int(self.col))

class RouteRequest(BaseModel):
    """Full routing job: every custom parameter from methods.md section 3+5."""

    model_config = ConfigDict(extra="forbid")

    sources: List[CellRef] = Field(min_length=1, max_length=64)
    target: CellRef
    weights: WeightsModel = Field(default_factory=WeightsModel)
    elevation_direction_threshold: float = Field(default=R.ELEVATION_DIRECTION_THRESHOLD, ge=0.0, le=50.0)
    roughness: RoughnessParams = Field(default_factory=RoughnessParams)
    obstacles: ObstacleParams = Field(default_factory=ObstacleParams)
    penalties: PenaltyExpressions = Field(default_factory=PenaltyExpressions)
    geology: GeologyPenalties = Field(default_factory=GeologyPenalties)
    max_expansions: Optional[int] = Field(default=None, ge=1, le=10_000_000)
    return_path_cells: bool = True
    max_path_cells: int = Field(default=20000, ge=1, le=200000)

    @field_validator("sources")
    @classmethod
    def _unique_sources(cls, v: List[CellRef]) -> List[CellRef]:
        seen = {(c.row, c.col) for c in v}
        if len(seen) != len(v):
            raise ValueError("sources must not contain duplicates")
        return v


class RouteResponse(BaseModel):
    """Serialised routing result."""

    model_config = ConfigDict(extra="forbid")

    reached: bool
    total_cost: Optional[float] = None
    path_length_m: Optional[float] = None
    path_cells: Optional[int] = None
    path: Optional[List[CellRef]] = None
    config_hash: str
    warnings: List[str] = Field(default_factory=list)


class CellCostResponse(BaseModel):
    """Per-cell cost breakdown for map visualisation."""

    model_config = ConfigDict(extra="forbid")

    row: int
    col: int
    valid: bool
    elevation_m: Optional[float] = None
    roughness_m: Optional[float] = None
    obstacle_density: Optional[float] = None
    roughness_cost: Optional[float] = None
    obstacle_cost: Optional[float] = None
    geology_cost: Optional[float] = None
    terrain_ir_cost: Optional[float] = None
    thermal_cost: Optional[float] = None
    config_hash: str


class DefaultsResponse(BaseModel):
    """Optimal defaults + enum choices for client UIs."""

    model_config = ConfigDict(extra="forbid")

    weights: WeightsModel
    elevation_direction_threshold: float
    roughness: RoughnessParams
    obstacles: ObstacleParams
    penalty_expressions: Dict[str, str]
    roughness_methods: List[str]
    obstacle_methods: List[str]
    neighborhood_radius_range: List[int]
    geology_codes: Dict[str, str]

app = FastAPI(
    title="Traverse Cost Routing API",
    version="1.0.0",
    description="Validated routing over the aligned Nili MTM 100 m stack. "
    "POST /route with any subset of parameters; omitted values fall back "
    "to the optimal defaults in routing.py.",
)

_MAPS: R.RasterMaps | None = None
_LAYERS_CACHE: Dict[str, Dict[str, np.ndarray]] = {}
_MAPS_LOCK = threading.Lock()


def get_maps() -> R.RasterMaps:
    """Thread-safe lazy loader for the aligned rasters."""
    global _MAPS
    if _MAPS is None:
        with _MAPS_LOCK:
            if _MAPS is None:
                try:
                    _MAPS = R.load_maps()
                except (FileNotFoundError, ValueError, ImportError) as exc:
                    raise HTTPException(status_code=500, detail=f"cannot load aligned rasters: {exc}") from exc
    assert _MAPS is not None
    return _MAPS


_PENALTY_ATTRS = (
    ("asc_penalty", "asc_penalty_func"),
    ("desc_penalty", "desc_penalty_func"),
    ("flat_penalty", "flat_penalty_func"),
    ("continuous_asc_penalty", "continuous_asc_penalty_func"),
    ("continuous_desc_penalty", "continuous_desc_penalty_func"),
    ("continuous_flat_penalty", "continuous_flat_penalty_func"),
    ("terrain_roughness_penalty", "terrain_roughnes_penalty_func"),
    ("thermal_swing_risk_penalty", "thermal_swing_risk_penalty_func"),
    ("obstacle_density_penalty", "obstacle_density_penalty_func"),
    ("terrain_type_ir_based_penalty", "terrain_type_IR_based_penalty_func"),
)


@contextmanager
def _applied_penalties(penalties: PenaltyExpressions) -> Iterator[None]:
    """Temporarily swap compiled penalty functions for custom expressions.

    Isolation is per-request via a module lock: routing keeps its globals,
    the API swaps them only for the duration of one job and restores the
    defaults afterwards, even on error.
    """
    saved = {attr: getattr(R, attr) for _, attr in _PENALTY_ATTRS}
    try:
        for field_name, attr in _PENALTY_ATTRS:
            raw = getattr(penalties, field_name)
            if raw is None:
                continue
            if isinstance(raw, (int, float)):
                const = float(raw)
                setattr(R, attr, (lambda _x, _c=const: _c))
            else:
                setattr(R, attr, R.compile_expression(raw))
        yield
    finally:
        for attr, fn in saved.items():
            setattr(R, attr, fn)


def _config_fingerprint(req: RouteRequest) -> str:
    payload = req.model_dump(mode="json")
    payload.pop("sources", None)
    payload.pop("target", None)
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def _method_str(value: object) -> str:
    """Unwrap a (str) Enum member to its plain value string."""
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)


def _request_to_cost_config(req: RouteRequest) -> R.CostConfig:
    return R.CostConfig(
        w_elevation=req.weights.w_elevation,
        w_continuous_elevation=req.weights.w_continuous_elevation,
        w_roughness=req.weights.w_roughness,
        w_obstacles=req.weights.w_obstacles,
        w_terrain_geology=req.weights.w_terrain_geology,
        w_terrain_ir=req.weights.w_terrain_ir,
        w_thermal=req.weights.w_thermal,
        elevation_direction_threshold=req.elevation_direction_threshold,
        roughness_method=_method_str(req.roughness.method),
        roughness_radius=req.roughness.neighborhood_radius,
        percentile_low=req.roughness.percentile_low,
        percentile_high=req.roughness.percentile_high,
        roughness_detrend=req.roughness.detrend,
        obstacle_method=_method_str(req.obstacles.method),
        obstacle_radius=req.obstacles.neighborhood_radius,
        obstacle_detrend=req.obstacles.detrend,
        residual_threshold_m=req.obstacles.residual_threshold_m,
        slope_threshold_deg=req.obstacles.slope_threshold_deg,
        tri_threshold_m=req.obstacles.tri_threshold_m,
    ).validate()


def _cell_layers(maps: R.RasterMaps, req: RouteRequest, cfg: R.CostConfig) -> Dict[str, np.ndarray]:
    """Precomputed layers, cached per config hash (thread-safe)."""
    key = _config_fingerprint(req)
    cached = _LAYERS_CACHE.get(key)
    if cached is None:
        with _applied_penalties(req.penalties):
            with _MAPS_LOCK:  # serialises global penalty swap + cache fill
                cached = _LAYERS_CACHE.get(key)
                if cached is None:
                    saved_geo = dict(R.terrain_type_geological_based_dict)
                    try:
                        R.terrain_type_geological_based_dict.clear()
                        R.terrain_type_geological_based_dict.update(
                            {int(k): float(p) for k, p in req.geology.penalties.items()}
                        )
                        cached = R.precompute_cell_layers(maps, cfg)
                    except ValueError as exc:
                        raise HTTPException(status_code=422, detail=str(exc)) from exc
                    finally:
                        R.terrain_type_geological_based_dict.clear()
                        R.terrain_type_geological_based_dict.update(saved_geo)
                    if len(_LAYERS_CACHE) >= 8:
                        _LAYERS_CACHE.pop(next(iter(_LAYERS_CACHE)))
                    _LAYERS_CACHE[key] = cached
    return cached

@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "service": "traverse-routing"}


@app.get("/defaults", response_model=DefaultsResponse)
def get_defaults() -> DefaultsResponse:
    """Optimal defaults + allowed values (drive client dropdowns)."""
    try:
        import json as _json
        from pathlib import Path as _Path

        lookup_path = R.ALIGNED_DIR / "geounit_lookup.json"
        codes = _json.loads(_Path(lookup_path).read_text()) if _Path(lookup_path).exists() else {}
    except (OSError, ValueError):
        codes = {}
    return DefaultsResponse(
        weights=WeightsModel(),
        elevation_direction_threshold=R.ELEVATION_DIRECTION_THRESHOLD,
        roughness=RoughnessParams(),
        obstacles=ObstacleParams(),
        penalty_expressions={
            "asc_penalty": R.asc_penalty_expr,
            "desc_penalty": R.desc_penalty_expr,
            "flat_penalty": R.flat_penalty_expr,
            "continuous_asc_penalty": R.continuous_asc_penalty_expr,
            "continuous_desc_penalty": R.continuous_desc_penalty_expr,
            "continuous_flat_penalty": R.continuous_flat_penalty_expr,
            "terrain_roughness_penalty": R.terrain_roughnes_penalty_expr,
            "thermal_swing_risk_penalty": R.thermal_swing_risk_penalty_expr,
            "obstacle_density_penalty": R.obstacle_density_penalty_expr,
            "terrain_type_ir_based_penalty": R.terrain_type_IR_based_penalty_expr,
        },
        roughness_methods=list(R._VALID_ROUGHNESS_METHODS),
        obstacle_methods=list(R._VALID_OBSTACLE_METHODS),
        neighborhood_radius_range=[R.MIN_NEIGHBORHOOD_RADIUS, R.MAX_NEIGHBORHOOD_RADIUS],
        geology_codes={str(k): str(v) for k, v in codes.items()},
    )


@app.post("/validate", response_model=Dict[str, object])
def validate_request(req: RouteRequest) -> Dict[str, object]:
    """Parse + validate a job without running the search; echo the plan."""
    maps = get_maps()
    try:
        cfg = _request_to_cost_config(req)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    problems: List[str] = []
    for cell in [*req.sources, req.target]:
        if not (0 <= cell.row < maps.height and 0 <= cell.col < maps.width):
            problems.append(f"cell ({cell.row}, {cell.col}) is outside {maps.height}x{maps.width}")
        elif not bool(maps.valid[cell.row, cell.col]):
            problems.append(f"cell ({cell.row}, {cell.col}) is nodata (impassable)")
    return {
        "valid": not problems,
        "problems": problems,
        "config_hash": _config_fingerprint(req),
        "cost_config": cfg.__dict__,
    }


@app.post("/route", response_model=RouteResponse)
def post_route(req: RouteRequest) -> RouteResponse:
    """Full pipeline: validate -> precompute layers -> Dijkstra -> path."""
    maps = get_maps()
    warnings: List[str] = []
    try:
        cfg = _request_to_cost_config(req)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    sources = [c.as_tuple() for c in req.sources]
    target = req.target.as_tuple()
    for label, (row, col) in [("source", s) for s in sources] + [("target", target)]:
        _r, _c = int(row), int(col)
        if not (0 <= _r < maps.height and 0 <= _c < maps.width):
            raise HTTPException(status_code=422, detail=f"{label} ({_r}, {_c}) outside {maps.height}x{maps.width}")
        if not bool(maps.valid[_r, _c]):
            raise HTTPException(status_code=422, detail=f"{label} ({_r}, {_c}) is nodata (impassable)")
    if req.obstacles.method == ObstacleMethod.multi_threshold and req.obstacles.multi_thresholds_m:
        warnings.append(f"multi_threshold ladder {req.obstacles.multi_thresholds_m} averaged to one density")
    layers = _cell_layers(maps, req, cfg)
    with _applied_penalties(req.penalties):
        with _MAPS_LOCK:
            saved_geo = dict(R.terrain_type_geological_based_dict)
            try:
                R.terrain_type_geological_based_dict.clear()
                R.terrain_type_geological_based_dict.update(
                    {int(k): float(p) for k, p in req.geology.penalties.items()}
                )
                try:
                    result = R.dijkstra(maps, layers, sources, cfg, target=target, max_expansions=req.max_expansions)
                except (TypeError, ValueError) as exc:
                    raise HTTPException(status_code=422, detail=str(exc)) from exc
            finally:
                R.terrain_type_geological_based_dict.clear()
                R.terrain_type_geological_based_dict.update(saved_geo)
    if not result.reached or not math.isfinite(float(result.distance[target])):
        return RouteResponse(reached=False, config_hash=_config_fingerprint(req), warnings=warnings + ["target unreachable"])
    try:
        path = R.reconstruct_path(result, target)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=f"path reconstruction failed: {exc}") from exc
    if len(path) > req.max_path_cells:
        warnings.append(f"path has {len(path)} cells; truncated to max_path_cells={req.max_path_cells}")
        path = path[: req.max_path_cells]
    return RouteResponse(
        reached=True,
        total_cost=float(result.distance[target]),
        path_length_m=R.path_length_m(path, maps.res_m),
        path_cells=len(path),
        path=[CellRef(row=r, col=c) for r, c in path] if req.return_path_cells else None,
        config_hash=_config_fingerprint(req),
        warnings=warnings,
    )


@app.get("/cell", response_model=CellCostResponse)
def get_cell(
    row: int = Query(ge=0),
    col: int = Query(ge=0),
    roughness_method: RoughnessMethod = RoughnessMethod.detrended_rms,
    roughness_radius: int = Query(default=1, ge=R.MIN_NEIGHBORHOOD_RADIUS, le=R.MAX_NEIGHBORHOOD_RADIUS),
    obstacle_radius: int = Query(default=1, ge=R.MIN_NEIGHBORHOOD_RADIUS, le=R.MAX_NEIGHBORHOOD_RADIUS),
    residual_threshold_m: float = Query(default=3.0, ge=0.05, le=100.0),
) -> CellCostResponse:
    """Inspect one cell's roughness / obstacle / IR / geology breakdown."""
    maps = get_maps()
    if not (0 <= row < maps.height and 0 <= col < maps.width):
        raise HTTPException(status_code=422, detail=f"cell ({row}, {col}) outside {maps.height}x{maps.width}")
    if not bool(maps.valid[row, col]):
                return CellCostResponse(row=row, col=col, valid=False, config_hash="nodata")
    try:
        rough_m = R.compute_roughness(
            maps.elevation, maps.valid, row, col,
            method=_method_str(roughness_method), neighborhood_radius=roughness_radius, res_m=maps.res_m,
        )
        dens = R.compute_obstacle_density(
            maps.elevation, maps.valid, row, col,
            neighborhood_radius=obstacle_radius, residual_threshold_m=residual_threshold_m, res_m=maps.res_m,
        )
        ir = float(np.clip(maps.day_ir[row, col] - maps.night_ir[row, col], -1.0, 1.0))
        code = int(maps.geo[row, col])
    except (TypeError, ValueError, IndexError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    blob = f"{row},{col},{_method_str(roughness_method)},{roughness_radius},{obstacle_radius},{residual_threshold_m}"
    return CellCostResponse(
        row=row, col=col, valid=True,
        elevation_m=float(maps.elevation[row, col]),
        roughness_m=float(rough_m),
        obstacle_density=float(dens),
        roughness_cost=float(R.terrain_roughnes_penalty_func(float(rough_m))),
        obstacle_cost=float(R.obstacle_density_penalty_func(float(dens))),
        geology_cost=float(R.terrain_type_geological_based_dict.get(code, R.DEFAULT_GEOLOGY_PENALTY)),
        terrain_ir_cost=float(R.terrain_type_IR_based_penalty_func(ir)),
        thermal_cost=float(R.thermal_swing_risk_penalty_func(abs(ir))),
        config_hash=hashlib.sha256(blob.encode()).hexdigest()[:16],
    )


if __name__ == "__main__":  # pragma: no cover - manual serve helper
    import uvicorn

    uvicorn.run("api:app", host="127.0.0.1", port=8000, reload=True)
