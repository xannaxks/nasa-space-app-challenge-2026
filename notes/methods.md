# Roughness and Obstacle Density Methods
## Context
Look at this notebook

```py
import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import geopandas as gpd
    import matplotlib.pyplot as plt
    from pathlib import Path
    import pyogrio

    return

@app.cell
def _():
    import numpy as np
    import pandas as pd
    import rasterio
    import os
    from pyproj import Transformer
    import copy

    return np, rasterio



@app.cell
def _():
    import ast
    import math
    import operator

    BINARY_OPERATORS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
    }

    UNARY_OPERATORS = {
        ast.UAdd: operator.pos,
        ast.USub: operator.neg,
    }

    FUNCTIONS = {
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
        "sqrt": math.sqrt,
        "log": math.log,
        "exp": math.exp,
        "abs": abs,
        "min": min,
        "max": max,
    }


    def compile_expression(expression):

        if len(expression) > 256:
            raise ValueError("Expression too long")

        tree = ast.parse(expression, mode="eval")

        if len(list(ast.walk(tree))) > 50:
            raise ValueError("Expression too complex")

        def evaluate(node, variables):

            if isinstance(node, ast.Constant):
                if type(node.value) not in (int, float):
                    raise ValueError("Only numeric constants allowed")
                return node.value

            if isinstance(node, ast.Name):
                if node.id not in variables:
                    raise ValueError(f"Unknown variable: {node.id}")
                return variables[node.id]

            if isinstance(node, ast.BinOp):
                op_type = type(node.op)

                if op_type not in BINARY_OPERATORS:
                    raise ValueError("Operator not allowed")

                left = evaluate(node.left, variables)
                right = evaluate(node.right, variables)

                if op_type is ast.Pow:
                    if abs(right) > 10:
                        raise ValueError("Exponent too large")

                return BINARY_OPERATORS[op_type](left, right)

            if isinstance(node, ast.UnaryOp):
                op_type = type(node.op)

                if op_type not in UNARY_OPERATORS:
                    raise ValueError("Unary operator not allowed")

                return UNARY_OPERATORS[op_type](
                    evaluate(node.operand, variables)
                )

            if isinstance(node, ast.Call):
                if not isinstance(node.func, ast.Name):
                    raise ValueError("Invalid function")

                name = node.func.id

                if name not in FUNCTIONS or node.keywords:
                    raise ValueError("Function not allowed")

                args = [
                    evaluate(arg, variables)
                    for arg in node.args
                ]

                return FUNCTIONS[name](*args)

            raise ValueError("Invalid expression")

        def function(x):

            result = evaluate(
                tree.body,
                {"x": float(x)}
            )

            if not math.isfinite(result):
                raise ValueError("Non-finite result")

            if result < 0:
                raise ValueError("Negative penalty")

            return result

        return function

    asc_penalty_expr = 0
    desc_penalty_expr = 0
    flat_penalty_expr = 0

    continuous_asc_penalty_expr = 0
    continuous_desc_penalty_expr = 0
    continuous_flat_penalty_expr = 0

    terrain_roughnes_penalty_expr = 0
    thermal_swing_risk_penalty_expr = 0
    obstacle_density_penalty_expr = 0
    terrain_type_IR_based_penalty_expr = 0


    asc_penalty_func = 0
    desc_penalty_func = 0
    flat_penalty_func = 0

    continuous_asc_penalty_func = 0
    continuous_desc_penalty_func = 0
    continuous_flat_penalty_func = 0

    terrain_roughnes_penalty_func = 0
    thermal_swing_risk_penalty_func = 0
    obstacle_density_penalty_func = 0
    terrain_type_IR_based_penalty_func = 0

    terrain_type_geological_based_dict: dict = {}
    return (
        asc_penalty_func,
        continuous_asc_penalty_func,
        continuous_desc_penalty_func,
        desc_penalty_func,
        flat_penalty_func,
        terrain_type_IR_based_penalty_func,
        terrain_type_geological_based_dict,
        thermal_swing_risk_penalty_func,
    )


@app.cell
def _(rasterio):
    def load(params: dict):
        elevation = rasterio.open('aligned/DTM_CTX_mosaic_MTM100m_norm01.tif')
        hillshade = rasterio.open('aligned/DTM_hillshade_MTM100m.tif')
        slope = rasterio.open('aligned/DTM_slope_deg_MTM100m.tif')
        day_ir = rasterio.open('aligned/THEMIS_Day_MTM100m_norm01.tif')
        night_ir = rasterio.open('aligned/THEMIS_Night_MTM100m_norm01.tif')
        geo = rasterio.open('aligned/GeoUnits_MTM100m.tif')

    load({})
    return


@app.cell
def _(INF, calc_cost, height, newi, newj, np, parent, self, width):
    # const int INF = 1000000000;
    # vector<vector<pair<int, int>>> adj;

    # void dijkstra(int s, vector<int> & d, vector<int> & p) {
    #     int n = adj.size();
    #     d.assign(n, INF);
    #     p.assign(n, -1);
    #     vector<bool> u(n, false);

    #     d[s] = 0;
    #     for (int i = 0; i < n; i++) {
    #         int v = -1;
    #         for (int j = 0; j < n; j++) {
    #             if (!u[j] && (v == -1 || d[j] < d[v]))
    #                 v = j;
    #         }

    #         if (d[v] == INF)
    #             break;

    #         u[v] = true;
    #         for (auto edge : adj[v]) {
    #             int to = edge.first;
    #             int len = edge.second;

    #             if (d[v] + len < d[to]) {
    #                 d[to] = d[v] + len;
    #                 p[to] = v;
    #             }
    #         }
    #     }
    # }

    class TraverState:
        def __init__(direction: int, run_distance: float, elevation_change: float):
            self.direction = direction # -1 DESC, 0 flat, 1 ASC
            self.run_distance = run_distance # distance covered without changing direction
            self.elevation_change = elevation_change # current transitions elevation change

    ti = np.array([0, 0, 1, -1, 1, -1, 1, -1])
    tj = np.array([1, -1, 0, 0, 1, -1, -1, 1])

    def get_path(from_i, from_j):
        path = []
        curi = from_i
        curj = from_j

        while True:
            path.append((from_i, from_j))
    
            _to = parent[curi, curj]
            if _to == -1:
                break

            curi += ti[_to]
            curj += tj[_to]

        path.append((curi, curj))    
        path.reverse()
    
        return path

    def dijkstra(_from):
        distance = np.array((height, width), INF)
        parent = np.array((height, width), -1)
        used = np.array((height, width), 0)

        for row, col in _from:
            distance[row, col] = 0

        for _i in range(height):
            for _j in range(width):
                vi = -1
                vj = -1
        
                for __i in range(height):
                    for __j in range(width):
                        if used[__i, __j] == 0 and (vi == -1 or distance[__i, __j] < distance[vi, vj]):
                            vi = __i
                            vj = __j

                if distance[vi, vj] == INF:
                    break

                used[vi, vj] = 1
                for _to in range(8):
                    new_i = vi + ti[_to]
                    new_j = vj + tj[_to]
                    cost = calc_cost(vi, vj, newi, newj)

                    if distance[new_i, new_j] > distance[vi, vj] + cost:
                        distance[new_i, new_j] = distance[vi, vj] + cost
                        parent[new_i, new_j] = _to
                
        return distance

    return


@app.cell
def _(
    ELEVATION_DIRECTION_THRESHOLD,
    W_CONTINUOUS_ELEVATION,
    W_ELEVATION,
    W_OBSTACLES,
    W_ROUGHNESS,
    W_TERRAIN_GEOLOGY,
    W_TERRAIN_IR,
    W_THERMAL,
    asc_penalty_func,
    continuous_asc_penalty_func,
    continuous_desc_penalty_func,
    day_ir,
    desc_penalty_func,
    elevation,
    flat_penalty_func,
    geo,
    get_distance,
    get_roughness_cost,
    night_ir,
    np,
    terrain_type_IR_based_penalty_func,
    terrain_type_geological_based_dict: dict,
    thermal_swing_risk_penalty_func,
):
    from dataclasses import dataclass

    @dataclass
    class TraverseState:
        direction: int = 0       # -1 descending, 0 flat, +1 ascending
        run_distance: float = 0.0
        run_elevation_change: float = 0.0


    @dataclass
    class EdgeInfo:
        elevation_change: float  # signed elevation difference, in meters
        slope_angle: float       # absolute slope angle, in degrees
        direction: int
        distance: float

        def get_distance(from_cell, to_cell):
            from_xy = np.asarray(geo.xy(from_cell), dtype=float)
            to_xy = np.asarray(geo.xy(to_cell), dtype=float)

            return float(np.linalg.norm(to_xy - from_xy))


    def get_edge_info(from_cell, to_cell):
        distance = get_distance(from_cell, to_cell)

        dh = float(elevation[to_cell] - elevation[from_cell])

        if distance == 0:
            raise ValueError("Adjacent cells must have nonzero distance")

        slope_angle = np.degrees(np.arctan2(abs(dh), distance))

        # Ignore tiny elevation fluctuations.
        if dh > ELEVATION_DIRECTION_THRESHOLD:
            direction = 1
        elif dh < -ELEVATION_DIRECTION_THRESHOLD:
            direction = -1
        else:
            direction = 0

        return EdgeInfo(
            elevation_change=dh,
            slope_angle=slope_angle,
            direction=direction,
            distance=distance
        )

    def get_traverse_state(previous_state, edge):
        if edge.direction == 0:
            return TraverseState()

        if edge.direction == previous_state.direction:
            return TraverseState(
                direction=edge.direction,
                run_distance=previous_state.run_distance + edge.distance,
                run_elevation_change=(
                    previous_state.run_elevation_change + abs(edge.elevation_change)
                )
            )

        # Direction changed: begin a new continuous run.
        return TraverseState(
            direction=edge.direction,
            run_distance=edge.distance,
            run_elevation_change=abs(edge.elevation_change)
        )

    def get_elevation_cost(edge):
        if edge.direction == -1:
            return desc_penalty_func(edge.slope_angle)

        if edge.direction == 0:
            return flat_penalty_func(edge.slope_angle)

        return asc_penalty_func(edge.slope_angle)

    def get_continuous_elevation_cost(previous_state, new_state):
        if new_state.direction == -1:
            old_penalty = continuous_desc_penalty_func(
                previous_state.run_distance
            )
            new_penalty = continuous_desc_penalty_func(
                new_state.run_distance
            )

        elif new_state.direction == 1:
            old_penalty = continuous_asc_penalty_func(
                previous_state.run_distance
            )
            new_penalty = continuous_asc_penalty_func(
                new_state.run_distance
            )

        else:
            return 0.0

        return max(0.0, new_penalty - old_penalty)


    def get_rougness_cost(to_cell):
        pass

    def get_terrain_type_geological_based_cost(cell):
        geo_val = geo[cell]
        return terrain_type_geological_based_dict[geo_val]

    def get_thermal_swing_risk_cost(cell):
        return thermal_swing_risk_penalty_func(day_ir[cell] - night_ir[cell])

    def get_obstacle_density_cost(to_cell):
        pass

    def get_terrain_type_IR_based_cost(cell):
        return terrain_type_IR_based_penalty_func(day_ir[cell] - night_ir[cell])

    def calc_cost(from_cell, to_cell, previous_state):

        edge = get_edge_info(from_cell, to_cell)

        new_state = get_traverse_state(previous_state, edge)

        # Edge-based penalties
        elevation_cost = get_elevation_cost(edge)

        continuous_cost = get_continuous_elevation_cost(
            previous_state,
            new_state
        )

        # Cell-based penalties
        terrain_geology_cost = get_terrain_type_geological_based_cost(to_cell)
        terrain_IR_cost = get_terrain_type_IR_based_cost(to_cell)
        roughness_cost = get_roughness_cost(to_cell)
        obstacle_density_cost = get_obstacle_density_cost(to_cell)
        thermal_swing_cost = get_thermal_swing_risk_cost(to_cell)

        local_penalties = (
            W_ELEVATION * elevation_cost
            + W_ROUGHNESS * roughness_cost
            + W_TERRAIN_GEOLOGY * terrain_geology_cost
            + W_TERRAIN_IR * terrain_IR_cost
            + W_THERMAL * thermal_swing_cost
            + W_OBSTACLES * obstacle_density_cost
        )

        # Local penalties are dimensionless.
        base_cost = edge.distance * (1.0 + local_penalties)

        # Continuity cost is an incremental, cumulative cost.
        total_cost = (
            base_cost
            + W_CONTINUOUS_ELEVATION * continuous_cost
        )

        return total_cost, new_state

    return (calc_cost,)


if __name__ == "__main__":
    app.run()

```

You might notice that most of the traverse cost functions are implemented except roughness cost and obstacle density cost, i want u to implement them, harden code, and add default values for custom parameters, details are below.

## Notes:
Save result as aggregated code in routing.py as regular .py file (not notebook).
Don't implement any functionality outside of specified.
Raster maps are here `aligned/`

## 1. Roughness Calculation Methods

| Method | Calculation concept | Advantages | Limitations |
|---|---|---|---|
| Standard deviation | Standard deviation of neighborhood elevations | Simple and fast | Confuses smooth slopes with roughness |
| Mean absolute deviation (MAD) | Mean absolute deviation from neighborhood mean or median | Easy to interpret | Can be sensitive to outliers when calculated around the mean |
| Median absolute deviation | Median absolute deviation from neighborhood median | Robust to outliers | Less sensitive to isolated hazards |
| Percentile range | Difference between configurable percentiles, e.g. P90 - P10 | Robust measure of elevation spread | Does not describe spatial arrangement |
| TRI (Riley) | RMS difference between center elevation and neighboring elevations | Established terrain ruggedness measure | Can be affected by local slope |
| TRI (Wilson) | Mean absolute elevation difference between center and neighbors | Simple alternative to RMS TRI | Can be affected by local slope |
| Maximum deviation | Maximum absolute elevation difference from center | Detects extreme local irregularities | Very sensitive to noise |
| Detrended RMS | RMS of residuals after fitting a local plane | Separates local irregularity from general slope | More computationally expensive |

**Recommended:** Detrended RMS as the primary method; P90-P10 and TRI as alternatives.

## 2. Obstacle Density Calculation Methods

| Method | What qualifies as an obstacle? | Calculation | Output |
|---|---|---|---|
| Elevation difference | Difference from central cell exceeds threshold | Qualifying neighbors / total valid neighbors | 0-1 |
| Detrended residual | Difference from fitted local plane exceeds threshold | Qualifying neighbors / total valid neighbors | 0-1 |
| Local slope | Local slope exceeds threshold | Qualifying neighbors / total valid neighbors | 0-1 |
| TRI threshold | Local TRI exceeds threshold | Qualifying neighbors / total valid neighbors | 0-1 |
| Multi-threshold density | Residual exceeds one of several severity thresholds | Calculate density separately for each threshold | Multiple 0-1 layers |

**Recommended:** Detrended residual threshold. It avoids treating an ordinary smooth hillside as a dense obstacle field.

## 3. Customizable Parameters

| Parameter | Roughness | Obstacle density | Description |
|---|:---:|:---:|---|
| `method` | Yes | Yes | Selected calculation method |
| `neighborhood_radius` | Yes | Yes | Number of cells from center (X) |
| `percentile_low` | Yes | No | Lower percentile, e.g. P10 |
| `percentile_high` | Yes | No | Upper percentile, e.g. P90 |
| `detrend` | Yes | Yes | Whether to remove the local plane |
| `residual_threshold_m` | No | Yes | Minimum residual magnitude to classify an obstacle |
| `slope_threshold_deg` | Optional | Yes | Slope threshold for obstacle classification |
| `tri_threshold_m` | Optional | Yes | TRI threshold for obstacle classification |

## 4. Code hardening
Harden all the methods, functions, algorithms.

## 5. Optimal default values
Define optimal default values for customizable parameters, including those ones:
 asc_penalty_expr = 0
    desc_penalty_expr = 0
    flat_penalty_expr = 0

    continuous_asc_penalty_expr = 0
    continuous_desc_penalty_expr = 0
    continuous_flat_penalty_expr = 0

    terrain_roughnes_penalty_expr = 0
    thermal_swing_risk_penalty_expr = 0
    obstacle_density_penalty_expr = 0
    terrain_type_IR_based_penalty_expr = 0


    asc_penalty_func = 0
    desc_penalty_func = 0
    flat_penalty_func = 0

    continuous_asc_penalty_func = 0
    continuous_desc_penalty_func = 0
    continuous_flat_penalty_func = 0

    terrain_roughnes_penalty_func = 0
    thermal_swing_risk_penalty_func = 0
    obstacle_density_penalty_func = 0
    terrain_type_IR_based_penalty_func = 0
except this one:

    terrain_type_geological_based_dict: dict = {}