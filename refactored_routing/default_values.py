#done
# ---------------------------------------------------------------------------
# Optimal default penalty expressions
# ---------------------------------------------------------------------------
# Calibrated for the aligned Nili MTM 100 m stack:
#   slope p50 ~3.2 deg, p90 ~11.4 deg, p98 ~21.4 deg, max ~36.6 deg;
#   IR day-night diff (0..1 scaled) p5..p95 ~ -0.58..+0.58, std ~0.35;
#   elevation std ~280 m over the mosaic.
#
# Slope penalties grow quadratically from a ~4 deg free-travel deadband
# (rover-class terrain) and saturate at +6 (impassable canyon walls score
# far above any plausible detour). Flat ground still pays a small linear
# rolling term. Continuous-climb penalties are convex in run distance so
# long unbroken climbs/descents cost extra per metre. Roughness/obstacle
# penalties saturate with x/(x+k) so single bad cells cannot overflow the
# path cost. Thermal/IR penalties are mild (|x| <= 1 by construction) so
# they nudge routes without dominating slope/roughness.
from typing import Dict

asc_penalty_expr = "min(6.0, 0.004 * max(0.0, x - 4.0) ** 2)"
desc_penalty_expr = "min(6.0, 0.0025 * max(0.0, x - 5.0) ** 2)"
flat_penalty_expr = "min(6.0, 0.02 * x)"

continuous_asc_penalty_expr = "0.00025 * x ** 2"
continuous_desc_penalty_expr = "0.00015 * x ** 2"
continuous_flat_penalty_expr = "0.0 * x"

terrain_roughnes_penalty_expr = "4.0 * x / (x + 3.0)"
thermal_swing_risk_penalty_expr = "1.5 * abs(x)"
obstacle_density_penalty_expr = "5.0 * x / (x + 0.35)"
terrain_type_IR_based_penalty_expr = "1.2 * abs(x)"

#: Human-readable GeoUnits names for codes 1..14 (code 0 = background).
#: Shown in API docs so users understand which unit they penalise.
GEOLOGY_UNIT_NAMES: Dict[int, str] = {
    1: "1 - Eolian bedform unit",
    2: "2 - Nili planum fan unit",
    3: "3 - Jezero fan 1 unit",
    4: "4 - Jezero fan 2 unit",
    5: "5 - Jezero floor unit",
    6: "6 - Lower etched unit",
    7: "7 - Nili planum 1 unit",
    8: "8 - Nili planum 2 unit",
    9: "9 - Rugged bright unit",
    10: "10 - Upper etched unit",
    11: "11 - Crater ejecta unit",
    12: "12 - Crater interior unit",
    13: "13 - Crater rim unit",
    14: "14 - Smooth unit",
}
#: Reasonable default per-unit penalties (dimensionless, 0..10, direct
#: lookup - no math curve). Smooth / fan / floor units are cheap;
#: eolian bedforms, rugged bright, crater rims/interiors are expensive.
DEFAULT_GEOLOGY_PENALTIES: Dict[int, float] = {
    1: 1.5,
    2: 0.5,
    3: 0.4,
    4: 0.4,
    5: 0.3,
    6: 0.8,
    7: 0.6,
    8: 0.6,
    9: 1.2,
    10: 0.9,
    11: 1.0,
    12: 1.3,
    13: 1.6,
    14: 0.2,
}
#: Per-geology-unit penalty coefficients (direct lookup, no math curve).
#: Pre-filled with ``DEFAULT_GEOLOGY_PENALTIES``; per-request overrides
#: swap this global (see api._cell_layers / post_route). Unknown codes
#: (e.g. 0 = background) fall back to ``DEFAULT_GEOLOGY_PENALTY``.
terrain_type_geological_based_dict: Dict[int, float] = dict(DEFAULT_GEOLOGY_PENALTIES)
DEFAULT_GEOLOGY_PENALTY = 0.5
#: Which map defines the "terrain type" penalty: IR day-night swing
#: (default, recommended), geological units, or both at once (allowed
#: but NOT recommended - the two signals overlap, so mixing
#: double-counts terrain texture; prefer exactly one of them).
_VALID_TERRAIN_SOURCES = ("geological_units", "ir_swing", "both")
DEFAULT_TERRAIN_SOURCE = "ir_swing"

# Dimensionless weights balancing the local penalty terms, and the
# incremental continuous-climb term. Slope dominates; obstacles and
# roughness follow; geology/IR/thermal only nudge.
W_ELEVATION = 1.0
W_CONTINUOUS_ELEVATION = 0.5
W_ROUGHNESS = 0.8
W_OBSTACLES = 1.0
W_TERRAIN_GEOLOGY = 0.6
W_TERRAIN_IR = 0.3
W_THERMAL = 0.3

#: Elevation change below this is "flat" (100 m cells, CTX DTM noise).
ELEVATION_DIRECTION_THRESHOLD = 1.0

#: Default roughness configuration: detrended RMS, 3x3 window.
ROUGHNESS_DEFAULTS = {
    "method": "detrended_rms",
    "neighborhood_radius": 1,
    "percentile_low": 10.0,
    "percentile_high": 90.0,
    "detrend": True,
    "slope_threshold_deg": 15.0,
    "tri_threshold_m": 4.0,
}

#: Default obstacle-density configuration: detrended-residual threshold.
OBSTACLE_DEFAULTS = {
    "method": "detrended_residual",
    "neighborhood_radius": 1,
    "detrend": True,
    "residual_threshold_m": 3.0,
    "slope_threshold_deg": 15.0,
    "tri_threshold_m": 4.0,
}
