"""FastAPI + Pydantic v2 service over :mod:`routing`.

Receives every tunable traverse-cost parameter, parses/validates it with
Pydantic, runs the hardened :mod:`routing` pipeline and serialises the
result as JSON. Run with ``uvicorn api:app --reload``.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import threading
import time
from contextlib import asynccontextmanager, contextmanager
from enum import Enum
from typing import Dict, Iterator, List, Optional

import numpy as np
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

import routing as R

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("traverse.api")
logging.getLogger("traverse.routing").setLevel(logging.INFO)

MAX_WAYPOINTS = 20
RATE_LIMIT = "20/minute"
MAX_ACTIVE_CONNECTIONS = 50

_active_connections = 0
_connections_lock = threading.Lock()


async def connection_gate(request: Request, call_next):
    """Cap concurrent HTTP connections; overflow gets 503 + Retry-After."""
    global _active_connections
    with _connections_lock:
        if _active_connections >= MAX_ACTIVE_CONNECTIONS:
            logger.warning("gate: REJECT %s %s (active=%d, max=%d)", request.method, request.url.path,
                           _active_connections, MAX_ACTIVE_CONNECTIONS)
            return JSONResponse(
                status_code=503,
                content={"detail": f"server busy: more than {MAX_ACTIVE_CONNECTIONS} active connections; retry shortly"},
                headers={"Retry-After": "5"},
            )
        _active_connections += 1
        current = _active_connections
    started = time.perf_counter()
    logger.info("http: -> %s %s (active=%d)", request.method, request.url.path, current)
    try:
        response = await call_next(request)
        logger.info("http: <- %s %s status=%d (%.2fs)", request.method, request.url.path,
                    response.status_code, time.perf_counter() - started)
        return response
    finally:
        with _connections_lock:
            _active_connections -= 1


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: load maps once. Shutdown: clear limiter + caches, close maps."""
    global _MAPS
    logger.info("startup: begin - loading aligned rasters")
    started = time.perf_counter()
    try:
        _MAPS = R.load_maps()
    except (FileNotFoundError, ValueError, ImportError) as exc:
        logger.error("startup: FAILED - cannot load aligned rasters: %s", exc)
        raise RuntimeError(f"startup failed: cannot load aligned rasters: {exc}") from exc
    logger.info("startup: complete grid=%dx%d res=%.1fm valid=%d (%.2fs)",
                _MAPS.height, _MAPS.width, _MAPS.res_m,
                int(np.count_nonzero(_MAPS.valid)), time.perf_counter() - started)
    try:
        yield
    finally:
        logger.info("shutdown: begin - clearing caches, limiter data, closing maps")
        n_layers = len(_LAYERS_CACHE)
        n_tiles = len(_MAP_TILE_CACHE)
        _LAYERS_CACHE.clear()
        _MAP_TILE_CACHE.clear()
        _MAPS = None
        try:
            limiter.reset()
            logger.info("shutdown: rate-limiter storage cleared")
        except (AttributeError, NotImplementedError, ValueError) as exc:
            logger.warning("shutdown: limiter reset skipped (%s)", exc)
        with _connections_lock:
            _active_connections = 0
        logger.info("shutdown: complete layer_cache=%d tile_cache=%d maps_closed=True connections=0", n_layers, n_tiles)

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


class TerrainSource(str, Enum):
    """Which map defines the terrain-type penalty.

    ``ir_swing`` (default, recommended): day-night IR difference texture.
    ``geological_units``: per-unit penalty coefficients from the GeoUnits map.
    ``both``: allowed but NOT recommended - the two texture signals overlap,
    so mixing double-counts terrain (each branch weight is halved).
    """

    ir_swing = "ir_swing"
    geological_units = "geological_units"
    both = "both"


class GeologyPenalties(BaseModel):
    """Per-unit geology penalties keyed by GeoUnits code ``1..14``.

    Direct coefficient lookup (no math curve, unlike the other penalties):
    each unit maps to a score in [0, 10]; unknown codes (0 = background)
    use ``default_penalty``. Only applied when ``terrain_source`` includes
    geological units; with the default ``ir_swing`` source these are stored
    but ignored.

    Units: 1 - Eolian bedform unit, 2 - Nili planum fan unit,
    3 - Jezero fan 1 unit, 4 - Jezero fan 2 unit, 5 - Jezero floor unit,
    6 - Lower etched unit, 7 - Nili planum 1 unit, 8 - Nili planum 2 unit,
    9 - Rugged bright unit, 10 - Upper etched unit, 11 - Crater ejecta unit,
    12 - Crater interior unit, 13 - Crater rim unit, 14 - Smooth unit.
    """

    model_config = ConfigDict(extra="forbid", use_enum_values=False)

    penalties: Dict[str, float] = Field(
        default_factory=lambda: {str(k): float(v) for k, v in R.DEFAULT_GEOLOGY_PENALTIES.items()},
        description="Per-unit penalty coefficients for GeoUnits codes 1..14 "
        "(1 - Eolian bedform, 2 - Nili planum fan, 3 - Jezero fan 1, "
        "4 - Jezero fan 2, 5 - Jezero floor, 6 - Lower etched, "
        "7 - Nili planum 1, 8 - Nili planum 2, 9 - Rugged bright, "
        "10 - Upper etched, 11 - Crater ejecta, 12 - Crater interior, "
        "13 - Crater rim, 14 - Smooth). Direct lookup, no math curve.",
    )
    default_penalty: float = Field(default=R.DEFAULT_GEOLOGY_PENALTY, ge=0.0, le=10.0)

    @field_validator("penalties")
    @classmethod
    def _check_codes(cls, v: Dict[str, float]) -> Dict[str, float]:
        if len(v) > 64:
            raise ValueError("at most 64 geology codes")
        checked: Dict[str, float] = {}
        for code, penalty in v.items():
            try:
                key = int(str(code).strip())
            except (TypeError, ValueError) as exc:
                raise ValueError(f"invalid geology code {code!r}") from exc
            if not 1 <= key <= 14:
                raise ValueError(f"geology code out of range (must be 1..14): {code!r}")
            checked[str(key)] = _finite_nonneg(f"geology[{key}]", penalty, 0.0, 10.0)
        missing = [str(c) for c in range(1, 15) if str(c) not in checked]
        if missing:
            raise ValueError(f"geology penalties missing codes {missing} (need all 1..14)")
        return checked


class CellRef(BaseModel):
    """One grid cell; validated against the map inside the endpoint."""

    model_config = ConfigDict(extra="forbid")

    row: int = Field(ge=0)
    col: int = Field(ge=0)

    def as_tuple(self) -> tuple[int, int]:
        return (int(self.row), int(self.col))

class RouteRequest(BaseModel):
    """Ordered route job: up to 20 waypoints + every custom cost parameter.

    All tuning fields fall back to the optimal ``routing.py`` defaults when
    omitted. The response chains Dijkstra legs between consecutive
    waypoints in input order (first->second->...->last) and aggregates
    them into one route.

    Terrain type: pick exactly ONE of ``ir_swing`` (default, recommended)
    or ``geological_units`` via ``terrain_source``. ``both`` is allowed but
    NOT recommended (overlapping texture signals double-count terrain).
    """

    model_config = ConfigDict(extra="forbid")

    waypoints: List[CellRef] = Field(min_length=2, max_length=MAX_WAYPOINTS)
    weights: WeightsModel = Field(default_factory=WeightsModel)
    terrain_source: TerrainSource = Field(
        default=TerrainSource.ir_swing,
        description="Which map defines the terrain-type penalty: 'ir_swing' "
        "(default, recommended), 'geological_units' (per-unit coefficients), "
        "or 'both' (allowed but NOT recommended - signals overlap).",
    )
    elevation_direction_threshold: float = Field(default=R.ELEVATION_DIRECTION_THRESHOLD, ge=0.0, le=50.0)
    roughness: RoughnessParams = Field(default_factory=RoughnessParams)
    obstacles: ObstacleParams = Field(default_factory=ObstacleParams)
    penalties: PenaltyExpressions = Field(default_factory=PenaltyExpressions)
    geology: GeologyPenalties = Field(default_factory=GeologyPenalties)
    max_expansions: Optional[int] = Field(default=None, ge=1, le=10_000_000)
    return_path_cells: bool = True
    max_path_cells: int = Field(default=20000, ge=1, le=200000)

    @field_validator("waypoints")
    @classmethod
    def _unique_waypoints(cls, v: List[CellRef]) -> List[CellRef]:
        seen = {(c.row, c.col) for c in v}
        if len(seen) != len(v):
            raise ValueError("waypoints must not contain duplicates")
        return v

    @property
    def sources(self) -> List[CellRef]:
        return self.waypoints[:-1]

    @property
    def target(self) -> CellRef:
        return self.waypoints[-1]


class TourLeg(BaseModel):
    """One Dijkstra leg of the ordered route."""

    model_config = ConfigDict(extra="forbid")

    start: CellRef
    end: CellRef
    reached: bool
    total_cost: Optional[float] = None
    path_length_m: Optional[float] = None
    path_cells: Optional[int] = None
    path: Optional[List[CellRef]] = None


class RouteResponse(BaseModel):
    """Serialised ordered-route result from the first to the last waypoint."""

    model_config = ConfigDict(extra="forbid")

    reached: bool
    visit_order: List[CellRef]
    total_cost: Optional[float] = None
    path_length_m: Optional[float] = None
    path_cells: Optional[int] = None
    path: Optional[List[CellRef]] = None
    legs: List[TourLeg] = Field(default_factory=list)
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
    geology_unit: Optional[str] = None
    terrain_ir_cost: Optional[float] = None
    thermal_cost: Optional[float] = None
    config_hash: str


class DefaultsResponse(BaseModel):
    """Optimal defaults + enum choices for client UIs."""

    model_config = ConfigDict(extra="forbid")

    weights: WeightsModel
    terrain_source: TerrainSource
    terrain_sources: List[str]
    elevation_direction_threshold: float
    roughness: RoughnessParams
    obstacles: ObstacleParams
    penalty_expressions: Dict[str, str]
    roughness_methods: List[str]
    obstacle_methods: List[str]
    neighborhood_radius_range: List[int]
    geology_penalties: Dict[str, float]
    geology_unit_names: Dict[str, str]
    geology_codes: Dict[str, str]

limiter = Limiter(key_func=get_remote_address, storage_uri="memory://")
app = FastAPI(
    title="Traverse Cost Routing API",
    version="2.0.0",
    description="Validated multi-waypoint traverse routing over the aligned "
    "Nili MTM 100 m stack. POST /route with waypoints (<=20) plus any "
    "subset of cost parameters; omitted values fall back to the optimal "
    "defaults in routing.py. Dijkstra legs are chained in waypoint order "
    "(first->second->...->last) and aggregated into one route.",
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.middleware("http")(connection_gate)

_MAPS: R.RasterMaps | None = None
_LAYERS_CACHE: Dict[str, Dict[str, np.ndarray]] = {}
_MAPS_LOCK = threading.Lock()


def get_maps() -> R.RasterMaps:
    """Return the startup-loaded maps (fails cleanly if startup failed)."""
    if _MAPS is None:
        raise HTTPException(status_code=500, detail="maps are not loaded (server still starting or startup failed)")
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
    custom = {name: getattr(penalties, name) for name, _ in _PENALTY_ATTRS
              if getattr(penalties, name) is not None}
    if custom:
        logger.info("penalties: applying custom curves %s", {k: (v if isinstance(v, (int, float)) else str(v)[:60]) for k, v in custom.items()})
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
        if custom:
            logger.info("penalties: restored %d default curve(s)", len(custom))


def _config_fingerprint(req: RouteRequest) -> str:
    payload = req.model_dump(mode="json")
    payload.pop("waypoints", None)
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
        terrain_source=_method_str(req.terrain_source),
        geology_penalties={int(k): float(v) for k, v in req.geology.penalties.items()},
        geology_default_penalty=req.geology.default_penalty,
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
    if cached is not None:
        logger.info("layers: cache HIT hash=%s (%d cached)", key, len(_LAYERS_CACHE))
        return cached
    logger.info("layers: cache MISS hash=%s - precomputing ...", key)
    started = time.perf_counter()
    if True:
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
                        if req.geology.penalties:
                            logger.info("layers: custom geology penalties for %d code(s)", len(req.geology.penalties))
                        cached = R.precompute_cell_layers(maps, cfg)
                    except ValueError as exc:
                        raise HTTPException(status_code=422, detail=f"invalid parameters: {exc}") from exc
                    finally:
                        R.terrain_type_geological_based_dict.clear()
                        R.terrain_type_geological_based_dict.update(saved_geo)
                    if len(_LAYERS_CACHE) >= 8:
                        evicted = next(iter(_LAYERS_CACHE))
                        _LAYERS_CACHE.pop(evicted)
                        logger.info("layers: evicted oldest cache entry hash=%s", evicted)
                    _LAYERS_CACHE[key] = cached
    logger.info("layers: ready hash=%s in %.2fs", key, time.perf_counter() - started)
    return cached

@app.get("/health")
@limiter.limit(RATE_LIMIT)
def health(request: Request) -> Dict[str, str]:
    maps = _MAPS
    return {
        "status": "ok",
        "service": "traverse-routing",
        "maps_loaded": str(maps is not None),
        "grid": f"{maps.height}x{maps.width}" if maps is not None else "not-loaded",
    }


@app.get("/defaults", response_model=DefaultsResponse)
@limiter.limit(RATE_LIMIT)
def get_defaults(request: Request) -> DefaultsResponse:
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
        terrain_source=TerrainSource.ir_swing,
        terrain_sources=list(R._VALID_TERRAIN_SOURCES),
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
        geology_penalties={str(k): float(v) for k, v in R.DEFAULT_GEOLOGY_PENALTIES.items()},
        geology_unit_names={str(k): v for k, v in R.GEOLOGY_UNIT_NAMES.items()},
        geology_codes={str(k): str(v) for k, v in codes.items()},
    )


@app.post("/validate", response_model=Dict[str, object])
@limiter.limit(RATE_LIMIT)
def validate_request(request: Request, req: RouteRequest) -> Dict[str, object]:
    """Parse + validate a route job without running the search; echo the plan."""
    client = request.client.host if request.client else "?"
    logger.info("validate: %d waypoint(s) from %s", len(req.waypoints), client)
    maps = get_maps()
    try:
        cfg = _request_to_cost_config(req)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"invalid parameters: {exc}") from exc
    problems: List[str] = []
    for idx, cell in enumerate(req.waypoints):
        if not (0 <= cell.row < maps.height and 0 <= cell.col < maps.width):
            logger.warning("validate: waypoint rejected")
            problems.append(f"waypoint {idx} ({cell.row}, {cell.col}) is outside {maps.height}x{maps.width}")
        elif not bool(maps.valid[cell.row, cell.col]):
            logger.warning("validate: waypoint rejected")
            problems.append(f"waypoint {idx} ({cell.row}, {cell.col}) is nodata (impassable)")
    logger.info("validate: valid=%s problems=%d hash=%s", not problems, len(problems), _config_fingerprint(req))
    if _method_str(req.terrain_source) == "both":
        problems_note = (
            "terrain_source='both' mixes IR-swing and geological-units terrain "
            "penalties; NOT recommended (overlapping signals double-count terrain). "
            "Prefer exactly one of 'ir_swing' or 'geological_units'."
        )
    else:
        problems_note = ""
    return {
        "valid": not problems,
        "problems": problems,
        "num_waypoints": len(req.waypoints),
        "terrain_source": _method_str(req.terrain_source),
        "terrain_warning": problems_note,
        "config_hash": _config_fingerprint(req),
        "cost_config": cfg.__dict__,
    }


@app.post("/route", response_model=RouteResponse)
@limiter.limit(RATE_LIMIT)
def post_route(request: Request, req: RouteRequest) -> RouteResponse:
    """Ordered multi-waypoint route: sequential Dijkstra legs in input order.

    Legs are computed first->second, second->third, ..., each with one
    Dijkstra search (early-stopped at its target), then concatenated into
    a single aggregated first-to-last path for frontend rendering.
    """
    job_started = time.perf_counter()
    client = request.client.host if request.client else "?"
    logger.info("route: start %d waypoint(s) from %s: %s",
                                len(req.waypoints), client, [(c.row, c.col) for c in req.waypoints])
    maps = get_maps()
    warnings: List[str] = []
    try:
        cfg = _request_to_cost_config(req)
        logger.info("route: params hash=%s rough=%s obst=%s terrain=%s", _config_fingerprint(req),
                    _method_str(req.roughness.method), _method_str(req.obstacles.method),
                    _method_str(req.terrain_source))
    except (TypeError, ValueError) as exc:
        logger.warning("route: invalid parameters: %s", exc)
        raise HTTPException(status_code=422, detail=f"invalid parameters: {exc}") from exc
    if _method_str(req.terrain_source) == "both":
        warnings.append(
            "terrain_source='both' mixes IR-swing and geological-units terrain "
            "penalties; NOT recommended (overlapping signals double-count terrain "
            "texture - each branch weight is halved). Prefer exactly one of "
            "'ir_swing' (recommended) or 'geological_units'."
        )
    elif _method_str(req.terrain_source) == "geological_units":
        warnings.append(
            "terrain_source='geological_units': using per-unit penalty coefficients "
            "(1 - Eolian bedform, 2 - Nili planum fan, 3 - Jezero fan 1, "
            "4 - Jezero fan 2, 5 - Jezero floor, 6 - Lower etched, "
            "7 - Nili planum 1, 8 - Nili planum 2, 9 - Rugged bright, "
            "10 - Upper etched, 11 - Crater ejecta, 12 - Crater interior, "
            "13 - Crater rim, 14 - Smooth)."
        )
    points = [c.as_tuple() for c in req.waypoints]
    for idx, (row, col) in enumerate(points):
        _r, _c = int(row), int(col)
        if not (0 <= _r < maps.height and 0 <= _c < maps.width):
            logger.warning("route: waypoint %d (%d,%d) outside %dx%d", idx, _r, _c, maps.height, maps.width)
            raise HTTPException(status_code=422, detail=f"waypoint {idx} ({_r}, {_c}) is outside {maps.height}x{maps.width}")
        if not bool(maps.valid[_r, _c]):
            logger.warning("route: waypoint %d (%d,%d) is nodata", idx, _r, _c)
            raise HTTPException(status_code=422, detail=f"waypoint {idx} ({_r}, {_c}) is nodata (impassable)")
    if req.obstacles.method == ObstacleMethod.multi_threshold and req.obstacles.multi_thresholds_m:
        warnings.append(f"multi_threshold ladder {req.obstacles.multi_thresholds_m} averaged to one density")
    layers = _cell_layers(maps, req, cfg)
    n = len(points)

    # Sequential legs in input order: one targeted Dijkstra per leg.
    full_cells: List[tuple[int, int]] = []
    legs: List[TourLeg] = []
    total_cost = 0.0
    all_reached = True
    visit_order = [CellRef(row=r, col=c) for r, c in points]
    for a in range(n - 1):
        b = a + 1
        start_ref = CellRef(row=points[a][0], col=points[a][1])
        end_ref = CellRef(row=points[b][0], col=points[b][1])
        logger.info("route: dijkstra leg %d->%d (%d,%d) -> (%d,%d)", a, b,
                    points[a][0], points[a][1], points[b][0], points[b][1])
        search_started = time.perf_counter()
        try:
            with _applied_penalties(req.penalties):
                with _MAPS_LOCK:
                    saved_geo = dict(R.terrain_type_geological_based_dict)
                    try:
                        R.terrain_type_geological_based_dict.clear()
                        R.terrain_type_geological_based_dict.update(
                            {int(k): float(p) for k, p in req.geology.penalties.items()}
                        )
                        result = R.dijkstra(maps, layers, [points[a]], cfg,
                                            target=points[b], max_expansions=req.max_expansions)
                    finally:
                        R.terrain_type_geological_based_dict.clear()
                        R.terrain_type_geological_based_dict.update(saved_geo)
        except (TypeError, ValueError) as exc:
            logger.warning("route: search failed: %s", exc)
            raise HTTPException(status_code=422, detail=f"invalid parameters: {exc}") from exc
        logger.info("route: leg %d->%d search done in %.2fs", a, b, time.perf_counter() - search_started)
        cost = float(result.distance[points[b]])
        if not math.isfinite(cost):
            all_reached = False
            legs.append(TourLeg(start=start_ref, end=end_ref, reached=False))
            warnings.append(f"leg {a}->{b} is unreachable under this cost model")
            logger.warning("route: leg %d->%d (%s -> %s) UNREACHABLE",
                           a, b, tuple(points[a]), tuple(points[b]))
            continue
        logger.info("route: leg %d->%d cost=%.1f - reconstructing path ...", a, b, cost)
        try:
            cells = R.reconstruct_path(result, points[b])
        except ValueError as exc:
            logger.error("route: leg %d->%d reconstruction failed: %s", a, b, exc)
            raise HTTPException(status_code=500, detail=f"path reconstruction failed: {exc}") from exc
        legs.append(TourLeg(
            start=start_ref, end=end_ref, reached=True, total_cost=cost,
            path_length_m=R.path_length_m(cells, maps.res_m), path_cells=len(cells),
            path=[CellRef(row=r, col=c) for r, c in cells] if req.return_path_cells else None,
        ))
        total_cost += cost
        full_cells.extend(cells if not full_cells else cells[1:])
    if not full_cells:
        logger.warning("route: FAILED - no leg of the route is reachable (%.2fs)", time.perf_counter() - job_started)
        return RouteResponse(
            reached=False, visit_order=visit_order,
            legs=legs, config_hash=_config_fingerprint(req),
            warnings=warnings + ["no leg of the route is reachable"],
        )
    if len(full_cells) > req.max_path_cells:
        warnings.append(f"route has {len(full_cells)} cells; truncated to max_path_cells={req.max_path_cells}")
        logger.warning("route: truncated %d cells to max_path_cells=%d", len(full_cells), req.max_path_cells)
        full_cells = full_cells[: req.max_path_cells]
    length_m = R.path_length_m(full_cells, maps.res_m)
    logger.info("route: done reached=%s legs=%d cells=%d length=%.1fm cost=%.1f (%.2fs)",
                all_reached, len(legs), len(full_cells), length_m, total_cost,
                time.perf_counter() - job_started)
    return RouteResponse(
        reached=all_reached,
        visit_order=visit_order,
        total_cost=total_cost if all_reached else None,
        path_length_m=length_m,
        path_cells=len(full_cells),
        path=[CellRef(row=r, col=c) for r, c in full_cells] if req.return_path_cells else None,
        legs=legs,
        config_hash=_config_fingerprint(req),
        warnings=warnings,
    )


@app.get("/cell", response_model=CellCostResponse)
@limiter.limit(RATE_LIMIT)
def get_cell(
    request: Request,
    row: int = Query(ge=0),
    col: int = Query(ge=0),
    roughness_method: RoughnessMethod = RoughnessMethod.detrended_rms,
    roughness_radius: int = Query(default=1, ge=R.MIN_NEIGHBORHOOD_RADIUS, le=R.MAX_NEIGHBORHOOD_RADIUS),
    obstacle_radius: int = Query(default=1, ge=R.MIN_NEIGHBORHOOD_RADIUS, le=R.MAX_NEIGHBORHOOD_RADIUS),
    residual_threshold_m: float = Query(default=3.0, ge=0.05, le=100.0),
    terrain_source: TerrainSource = TerrainSource.ir_swing,
) -> CellCostResponse:
    """Inspect one cell's roughness / obstacle / IR / geology breakdown."""
    logger.info("cell: (%d,%d) rough=%s r=%s obst_r=%s terrain=%s", row, col,
                _method_str(roughness_method), roughness_radius, obstacle_radius,
                _method_str(terrain_source))
    maps = get_maps()
    if not (0 <= row < maps.height and 0 <= col < maps.width):
        logger.warning("cell: (%d,%d) outside %dx%d", row, col, maps.height, maps.width)
        raise HTTPException(status_code=422, detail=f"cell ({row}, {col}) outside {maps.height}x{maps.width}")
    if not bool(maps.valid[row, col]):
        logger.info("cell: (%d,%d) nodata", row, col)
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
        geo_cost = float(R.get_terrain_type_geological_based_cost(maps, (row, col)))
    except (TypeError, ValueError, IndexError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    blob = f"{row},{col},{_method_str(roughness_method)},{roughness_radius},{obstacle_radius},{residual_threshold_m},{_method_str(terrain_source)}"
    return CellCostResponse(
        row=row, col=col, valid=True,
        elevation_m=float(maps.elevation[row, col]),
        roughness_m=float(rough_m),
        obstacle_density=float(dens),
        roughness_cost=float(R.terrain_roughnes_penalty_func(float(rough_m))),
        obstacle_cost=float(R.obstacle_density_penalty_func(float(dens))),
        geology_cost=geo_cost,
        geology_unit=R.GEOLOGY_UNIT_NAMES.get(code, f"{code} - Unknown unit"),
        terrain_ir_cost=float(R.terrain_type_IR_based_penalty_func(ir)),
        thermal_cost=float(R.thermal_swing_risk_penalty_func(abs(ir))),
        config_hash=hashlib.sha256(blob.encode()).hexdigest()[:16],
    )


RASTER_FILES: Dict[str, str] = {
    "dtm": "DTM_CTX_mosaic_MTM100m_norm01.tif",
    "elevation": "DTM_CTX_mosaic_MTM100m_norm01.tif",
    "slope": "DTM_slope_deg_MTM100m.tif",
    "geology": "GeoUnits_MTM100m.tif",
    "day_ir": "THEMIS_Day_MTM100m_norm01.tif",
    "night_ir": "THEMIS_Night_MTM100m_norm01.tif",
    "hillshade": "DTM_hillshade_MTM100m.tif",
}

MAP_TILE_PX = 256
_MAP_TILE_CACHE: Dict[tuple, bytes] = {}
_MAP_TILE_LOCK = threading.Lock()


def _resolve_layer(layer: str) -> str:
    if not isinstance(layer, str):
        raise HTTPException(status_code=422, detail="layer must be a string")
    key = layer.strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "dtm_elevation": "dtm", "elevation_norm01": "dtm", "dem": "dtm",
        "slope_deg": "slope", "slope_degree": "slope",
        "geounits": "geology", "geo": "geology", "geological_units": "geology",
        "day": "day_ir", "dayir": "day_ir", "ir_day": "day_ir", "themis_day": "day_ir",
        "night": "night_ir", "nightir": "night_ir", "ir_night": "night_ir", "themis_night": "night_ir",
        "shade": "hillshade",
    }
    key = aliases.get(key, key)
    if key not in RASTER_FILES:
        raise HTTPException(
            status_code=422,
            detail=f"unknown layer {layer!r}. Valid: {sorted(RASTER_FILES)}",
        )
    return key


def _read_aligned(layer: str) -> np.ndarray:
    path = R.ALIGNED_DIR / RASTER_FILES[layer]
    if R.rasterio is None:  # pragma: no cover
        raise HTTPException(status_code=500, detail="rasterio is not installed")
    try:
        with R.rasterio.open(path) as src:
            return src.read(1).astype(float)
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=f"cannot read {path.name}: {exc}") from exc


def _norm_for_display(layer: str, tile: np.ndarray) -> np.ndarray:
    finite = tile[np.isfinite(tile)]
    if finite.size == 0:
        return np.zeros_like(tile, dtype=float)
    if layer in ("dtm", "elevation", "day_ir", "night_ir"):
        lo, hi = float(np.percentile(finite, 2)), float(np.percentile(finite, 98))
    elif layer == "slope":
        lo, hi = 0.0, float(np.percentile(finite, 98)) or 1.0
    elif layer == "geology":
        return np.clip(tile / 14.0, 0.0, 1.0)
    else:  # hillshade uint8 0..255
        lo, hi = 0.0, 255.0
    if not math.isfinite(lo) or not math.isfinite(hi) or hi <= lo:
        return np.zeros_like(tile, dtype=float)
    return np.clip((tile - lo) / (hi - lo), 0.0, 1.0)


def _render_tile_png(layer: str, tile: np.ndarray) -> bytes:
    import io
    import struct
    import zlib

    key = (layer, tile.shape, float(np.nanmean(tile)) if tile.size else 0.0,
           float(np.nanstd(tile)) if tile.size else 0.0)
    with _MAP_TILE_LOCK:
        hit = _MAP_TILE_CACHE.get(key)
    if hit is not None:
        return hit
    norm = _norm_for_display(layer, np.nan_to_num(tile.astype(float), nan=0.0))
    small = np.clip((norm * 255.0), 0, 255).astype(np.uint8)
    # Nearest-neighbour upscale/downscale to 256x256 without new deps.
    h, w = small.shape
    ys = np.clip((np.arange(MAP_TILE_PX) * h) // MAP_TILE_PX, 0, max(h - 1, 0))
    xs = np.clip((np.arange(MAP_TILE_PX) * w) // MAP_TILE_PX, 0, max(w - 1, 0))
    img = small[ys][:, xs]
    geo_img = None
    if layer == "geology":
        raw_codes = np.clip(np.nan_to_num(tile.astype(float), nan=0.0).astype(int), 0, 14)
        gys = np.clip((np.arange(MAP_TILE_PX) * raw_codes.shape[0]) // MAP_TILE_PX, 0, max(raw_codes.shape[0] - 1, 0))
        gxs = np.clip((np.arange(MAP_TILE_PX) * raw_codes.shape[1]) // MAP_TILE_PX, 0, max(raw_codes.shape[1] - 1, 0))
        geo_img = raw_codes[gys][:, gxs]
    if layer == "geology":
        palette = ((68, 1, 84), (59, 82, 139), (33, 145, 140), (94, 201, 98),
                   (253, 231, 37), (239, 138, 98), (215, 25, 28), (153, 52, 4))
        assert geo_img is not None
        codes = np.clip(geo_img.astype(int), 0, 14)
        rgb = np.zeros((MAP_TILE_PX, MAP_TILE_PX, 3), dtype=np.uint8)
        for code in range(1, 15):
            rgb[codes == code] = palette[(code - 1) % len(palette)]
    elif layer in ("day_ir", "night_ir"):
        rgb = np.stack([img, img // 2 + 64, 255 - img // 2], axis=-1).astype(np.uint8)
    elif layer == "slope":
        rgb = np.stack([img, 255 - img, np.full_like(img, 60)], axis=-1).astype(np.uint8)
    elif layer == "hillshade":
        rgb = np.stack([img, img, img], axis=-1).astype(np.uint8)
    else:  # dtm terrain tint
        rgb = np.stack([img // 2 + 40, img, 255 - img], axis=-1).astype(np.uint8)
    raw = b"".join(b"\x00" + rgb[r].tobytes() for r in range(MAP_TILE_PX))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", MAP_TILE_PX, MAP_TILE_PX, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 6))
        + chunk(b"IEND", b"")
    )
    with _MAP_TILE_LOCK:
        if len(_MAP_TILE_CACHE) >= 512:
            _MAP_TILE_CACHE.pop(next(iter(_MAP_TILE_CACHE)))
        _MAP_TILE_CACHE[key] = png
    return png


@app.get("/maps", response_model=Dict[str, object])
@limiter.limit(RATE_LIMIT)
def list_maps(request: Request) -> Dict[str, object]:
    """Catalogue of frontend-renderable raster layers with grid metadata."""
    maps = get_maps()
    return {
        "layers": sorted(RASTER_FILES),
        "grid": {"height": maps.height, "width": maps.width, "res_m": maps.res_m},
        "tile": {"size_px": MAP_TILE_PX, "usage": "/maps/{layer}/tiles/{z}/{x}/{y}.png, /maps/{layer}/data?downsample="},
    }


@app.get("/maps/{layer}/info", response_model=Dict[str, object])
@limiter.limit(RATE_LIMIT)
def map_info(request: Request, layer: str) -> Dict[str, object]:
    """Per-layer statistics + value range for frontend colour scales."""
    started = time.perf_counter()
    logger.info("map_info: layer=%s", layer)
    key = _resolve_layer(layer)
    arr = _read_aligned(key)
    finite = arr[np.isfinite(arr)]
    if finite.size == 0:
        raise HTTPException(status_code=500, detail=f"layer {key!r} has no finite values")
    stats = {
        "layer": key,
        "file": RASTER_FILES[key],
        "dtype": str(arr.dtype),
        "shape": [int(arr.shape[0]), int(arr.shape[1])],
        "min": float(finite.min()),
        "max": float(finite.max()),
        "mean": float(finite.mean()),
        "percentiles": {str(p): float(np.percentile(finite, p)) for p in (2, 5, 25, 50, 75, 95, 98)},
    }
    logger.info("map_info: %s done in %.2fs", key, time.perf_counter() - started)
    return stats


@app.get("/maps/{layer}/data")
@limiter.limit(RATE_LIMIT)
def map_data(
    request: Request,
    layer: str,
    downsample: int = Query(default=4, ge=1, le=16),
    row0: int = Query(default=0, ge=0),
    col0: int = Query(default=0, ge=0),
    rows: int = Query(default=0, ge=0, le=2048),
    cols: int = Query(default=0, ge=0, le=2048),
) -> Dict[str, object]:
    """Downsampled raster values as nested lists for canvas rendering.

    ``downsample=4`` returns the full 565x594 grid at ~141x149. Pass
    ``row0/col0/rows/cols`` for windowed panning. NaN serialises as null.
    """
    key = _resolve_layer(layer)
    arr = _read_aligned(key)
    height, width = arr.shape
    if row0 >= height or col0 >= width:
        raise HTTPException(status_code=422, detail=f"window origin ({row0}, {col0}) outside {height}x{width}")
    r1 = height if rows == 0 else min(height, row0 + rows)
    c1 = width if cols == 0 else min(width, col0 + cols)
    if r1 <= row0 or c1 <= col0:
        raise HTTPException(status_code=422, detail="empty window: check row0/col0/rows/cols")
    window = arr[row0:r1:downsample, col0:c1:downsample].astype(float)
    return {
        "layer": key,
        "row0": row0, "col0": col0, "rows": int(r1 - row0), "cols": int(c1 - col0),
        "downsample": downsample,
        "values": np.where(np.isfinite(window), window, np.nan).tolist(),
    }


@app.get("/maps/{layer}/tiles/{z}/{x}/{y}.png")
@limiter.limit(RATE_LIMIT)
def map_tile(request: Request, layer: str, z: int, x: int, y: int) -> Response:
    """Slippy-map PNG tile (Web-Mercator-free: plain grid tiles for Leaflet)."""
    if not (0 <= z <= 6):
        raise HTTPException(status_code=422, detail="z must be within [0, 6]")
    key = _resolve_layer(layer)
    n = 2**z
    if not (0 <= x < n and 0 <= y < n):
        raise HTTPException(status_code=422, detail=f"tile ({z}, {x}, {y}) out of range")
    arr = _read_aligned(key)
    height, width = arr.shape
    r0, r1 = (y * height) // n, ((y + 1) * height) // n
    c0, c1 = (x * width) // n, ((x + 1) * width) // n
    tile = arr[r0:r1, c0:c1]
    if tile.size == 0:
        raise HTTPException(status_code=422, detail="empty tile")
    png = _render_tile_png(key, tile)
    return Response(content=png, media_type="image/png")


@app.get("/maps/geology/vector.geojson")
@limiter.limit(RATE_LIMIT)
def geology_vector(
    request: Request,
    simplified: bool = Query(default=True),
    code: Optional[int] = Query(default=None, ge=1, le=14),
    minx: Optional[float] = Query(default=None),
    miny: Optional[float] = Query(default=None),
    maxx: Optional[float] = Query(default=None),
    maxy: Optional[float] = Query(default=None),
    limit: Optional[int] = Query(default=None, ge=1, le=R.GEOLOGY_VECTOR_MAX_FEATURES),
) -> Dict[str, object]:
    """Aggregated GeoUnits_v1 vector map as GeoJSON (MTM metres, NOT lon/lat).

    Serves ``aligned/GeoUnits_vector_MTM100m[_simplified].geojson``: all 1304
    unit polygons with every native GDB column plus ``_layer``/``_code``.
    Defaults to the 25 m-simplified variant (~3.4 MB); ``simplified=false``
    serves full resolution (~70 MB). Filter by unit ``code`` 1..14 and/or a
    ``minx/miny/maxx/maxy`` viewport window (MTM metres) to shrink payloads.
    The frontend plots these coordinates directly on the MTM grid tiles.
    """
    started = time.perf_counter()
    bbox = None
    if (minx, miny, maxx, maxy) != (None, None, None, None):
        if None in (minx, miny, maxx, maxy):
            raise HTTPException(status_code=422, detail="bbox needs all of minx, miny, maxx, maxy")
        bbox = (minx, miny, maxx, maxy)
    logger.info("geology_vector: simplified=%s code=%s bbox=%s limit=%s", simplified, code, bbox, limit)
    try:
        geojson = R.load_geology_vector_geojson(
            simplified=bool(simplified), code=code, bbox=bbox, limit=limit,
        )
    except (TypeError, ValueError) as exc:
        logger.warning("geology_vector: invalid parameters: %s", exc)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        logger.error("geology_vector: missing file: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    logger.info("geology_vector: %d features in %.2fs", len(geojson["features"]), time.perf_counter() - started)
    return geojson


@app.get("/maps/geology/vector/info", response_model=Dict[str, object])
@limiter.limit(RATE_LIMIT)
def geology_vector_info(request: Request) -> Dict[str, object]:
    """Export sidecar: CRS, bounds, per-symbol counts/areas (map legend data)."""
    try:
        return R.load_geology_vector_stats()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=f"cannot parse stats: {exc}") from exc


if __name__ == "__main__":  # pragma: no cover - manual serve helper
    import uvicorn

    uvicorn.run("api:app", host="127.0.0.1", port=8000, reload=True)
