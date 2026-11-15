# Jezero & Nili: Super Customizable Least-Cost Route Planner for Martian Exploration

## 1. Project Overview

Nili Planum and Jezero Crater preserve some of the most valuable geological records of ancient water activity, sedimentary processes, and planetary crust formation on Mars. Exploring these regions can provide important insights into the planet's geological history and potential habitability.

However, planning exploration routes across Martian terrain is considerably more complicated than finding the shortest distance between two locations. A route that appears geographically optimal might expose a rover to excessive slopes, difficult terrain, obstacles, or unfavorable thermal conditions. Furthermore, different exploration vehicles and scientific missions have different capabilities, limitations, and priorities.

Our project addresses this challenge by developing an interactive, highly customizable least-cost route planner that helps users identify suitable traversal routes across selected Martian regions.

Instead of relying exclusively on geographical distance, our system evaluates multiple terrain and environmental characteristics, allowing users to define what makes a route expensive according to their particular mission requirements.

## 2. What Does It Do and How Does It Work?

Our platform combines planetary datasets, terrain analysis, customizable cost modeling, and graph-based pathfinding into one interactive application.

**Planetary Data Visualization**

Users can explore different types of Martian map datasets through a layered map interface. Instead of presenting terrain as a single visualization, we provide separate, composable layers representing elevation, geological formations, infrared-derived terrain characteristics, and other environmental information.

This allows users to inspect different characteristics of the landscape, compare datasets, and understand the environmental conditions surrounding their selected locations.

**Terrain Analysis and Cost Modeling**

The backend processes planetary raster datasets and derives several terrain characteristics, including elevation changes, local roughness, potential obstacles, geological classifications, and thermal variations.

Each characteristic contributes to the traversal cost according to a configurable penalty function and user-defined weight.

The resulting cost surface represents how expensive it is to traverse different parts of the terrain. Users can modify the cost model to prioritize particular conditions, effectively creating different optimization strategies for different exploration scenarios.

**Least-Cost Route Calculation**

After configuring the parameters and selecting starting and destination locations, users can request a route.

Our system models the terrain as a weighted grid graph, where raster cells represent traversable locations and movement between neighboring cells incurs a cost based on the underlying terrain characteristics.

We use Dijkstra's shortest-path algorithm to find the minimum-cost route through this weighted representation.

The resulting route is displayed on the interactive map, allowing users to compare the proposed path against the underlying planetary datasets.

## 3. Customizable Parameters

One of the central features of our project is the ability to customize nearly every major component of the cost model.

We recognize that there is no universally optimal exploration route. A lightweight rover, a heavy scientific rover, and a hypothetical crewed expedition would have different capabilities and operational requirements. Even two rovers with similar hardware might prioritize different objectives depending on their scientific mission.

Our customization system allows users to represent these differences through parameter weights, terrain-analysis methods, thresholds, and penalty functions.

### A. Cost Weights

Users can assign different importance values to individual traversal factors.

- **Elevation Weight:** Controls the importance of elevation-related traversal penalties, including climbing, descending, and flat-terrain movement.
- **Continuous Elevation Weight:** Controls the influence of continuous elevation changes, accounting for cumulative ascent and descent rather than considering only individual elevation transitions.
- **Roughness Weight:** Determines how strongly uneven and irregular terrain affects traversal cost.
- **Obstacle Weight:** Controls the penalty associated with potentially hazardous terrain features and detected obstacles.
- **Geological Terrain Weight:** Determines how much geological classifications influence route selection.
- **Infrared Terrain Weight:** Controls the influence of terrain characteristics derived from infrared observations.
- **Thermal Weight:** Determines the importance of thermal variations and potential temperature-related traversal risks.

Increasing a weight makes its corresponding factor more influential in the overall route cost, while decreasing it allows the planner to prioritize other characteristics.

### B. Terrain Data Sources

Users can select which terrain classification source contributes to the cost model:

- **Geological Units:** Uses geological mapping to distinguish different surface formations and assign corresponding traversal penalties.
- **Infrared-derived Terrain (IR Swing):** Uses infrared-derived information to distinguish terrain characteristics and associated traversal costs.
- **Combined Sources:** Allows both geological and infrared-derived information to contribute to the terrain assessment.

### C. Elevation Analysis

Elevation-related costs account for different movement directions and cumulative terrain changes.

- **Elevation Direction Threshold:** Defines the threshold used to distinguish meaningful elevation changes when evaluating ascending, descending, and flat movement.
- **Ascending Penalty:** Penalizes uphill movement, with configurable nonlinear behavior.
- **Descending Penalty:** Accounts for the potential difficulty of downhill traversal.
- **Flat Terrain Penalty:** Allows a separate cost model for relatively flat movement.
- **Continuous Ascending Penalty:** Accounts for cumulative uphill elevation changes.
- **Continuous Descending Penalty:** Accounts for cumulative downhill elevation changes.

The penalty functions can be customized to represent different assumptions about how a particular explorer handles elevation changes.

### D. Terrain Roughness Analysis

Terrain roughness describes the local irregularity of the Martian surface. Different measurement techniques can produce different assessments of terrain difficulty.

Our system supports multiple roughness calculation methods:

- **Standard Deviation (STD):** Measures the dispersion of elevation values within a neighborhood.
- **Median Absolute Deviation (MAD):** Provides a robust measure of elevation variability that is less sensitive to extreme values.
- **Median Absolute Deviation from the Median (MEDAD):** Measures deviations relative to the local median elevation.
- **Percentile Range:** Measures the difference between selected elevation percentiles, reducing sensitivity to extreme outliers.
- **Terrain Ruggedness Index (TRI – Riley):** Estimates terrain ruggedness through elevation differences between neighboring cells.
- **Terrain Ruggedness Index (TRI – Wilson):** Provides an alternative terrain ruggedness calculation.
- **Maximum Deviation:** Measures the largest local elevation deviation.
- **Detrended Root Mean Square (Detrended RMS):** Estimates local surface irregularity after removing the general elevation trend.

Additional configuration options include:

- **Neighborhood Radius:** Controls the spatial area used for local terrain analysis. Our implementation supports radii from 1 to 4 cells.
- **Lower and Upper Percentiles:** Define the percentile range used in percentile-based roughness calculations.
- **Detrending:** Determines whether the general local elevation trend is removed before calculating roughness.
- **Slope Threshold:** Defines a slope threshold for identifying potentially difficult terrain.
- **TRI Threshold:** Defines the terrain ruggedness threshold used in terrain classification.

### E. Obstacle Detection

Obstacles can significantly affect rover mobility and mission reliability. Our system supports multiple methods for identifying potentially hazardous terrain.

Available methods include:

- **Elevation Difference:** Detects potentially problematic elevation differences between neighboring cells.
- **Detrended Residual:** Identifies local elevation deviations after removing the surrounding terrain trend.
- **Local Slope:** Uses terrain inclination to identify potentially difficult traversal areas.
- **TRI Threshold:** Uses terrain ruggedness measurements to identify areas exceeding a selected threshold.
- **Multiple Thresholds:** Allows several elevation thresholds to be considered when identifying potential obstacles.

Users can also configure the neighborhood radius, detrending behavior, residual threshold, slope threshold, and TRI threshold.

### F. Geological Penalties

Different geological formations may present different traversal characteristics. Our system supports individual penalties for 14 mapped geological units.

The available units include:

| Geological unit      | Code  | Default penalty |
| -------------------- | ----- | --------------- |
| Eolian bedform unit  | Aeb   | 1.5             |
| Nili Planum fan unit | Hnpf  | 0.5             |
| Jezero fan 1 unit    | NHjf1 | 0.4             |
| Jezero fan 2 unit    | NHjf2 | 0.4             |
| Jezero floor unit    | Njf   | 0.3             |
| Lower etched unit    | Nle   | 0.8             |
| Nili Planum 1 unit   | Nnp1  | 0.6             |
| Nili Planum 2 unit   | Nnp2  | 0.6             |
| Rugged bright unit   | Nrb   | 1.2             |
| Upper etched unit    | Nue   | 0.9             |
| Crater ejecta unit   | ce    | 1.0             |
| Crater interior unit | ci    | 1.3             |
| Crater rim unit      | cr    | 1.6             |
| Smooth unit          | su    | 0.2             |

These values represent configurable cost assumptions rather than definitive measurements of the physical danger of each geological formation. Users can adjust them according to their mission objectives and available scientific evidence.

### G. Infrared and Thermal Penalties

Our cost model also considers infrared-derived terrain characteristics and thermal variations.

- **Thermal Swing Penalty:** Accounts for thermal variations that may influence exploration conditions and equipment operation.
- **Infrared Terrain Penalty:** Assigns additional costs based on infrared-derived terrain characteristics.

Both factors have independently configurable weights and penalty functions, allowing users to decide how important these conditions are for their particular exploration scenario.

### H. Custom Penalty Functions

Beyond adjusting weights and thresholds, our system provides configurable mathematical penalty expressions for different traversal factors.

For example, users can define nonlinear penalties that increase rapidly after a certain elevation or obstacle threshold is exceeded.

This is important because traversal difficulty is not necessarily proportional to the measured terrain characteristic. A small increase in slope might be manageable for one rover but significantly more expensive for another.

By supporting configurable penalty expressions, we allow the cost model to represent different assumptions about vehicle capabilities and mission requirements.

## 4. What Are the Benefits?

Our solution provides several benefits for planetary exploration planning:

- **Mission-specific optimization:** Users can define different cost models according to the capabilities and priorities of their exploration vehicles.
- **More informed route selection:** Routes consider multiple terrain and environmental characteristics rather than geographical distance alone.
- **Flexible exploration strategies:** Researchers can experiment with different parameter configurations and compare their resulting routes.
- **Unified planetary visualization:** Multiple planetary datasets can be inspected through a layered interface, making it easier to understand the relationship between terrain characteristics and route decisions.
- **Extensibility:** The modular cost model allows additional datasets, terrain-analysis techniques, and mission-specific constraints to be incorporated.
- **Scientific exploration support:** Geological information can contribute to route planning, helping users investigate how scientific objectives and traversal requirements interact.

## 5. What Makes Our Project Creative and Different?

The main creative aspect of our project is that we do not assume that a single cost function can represent every exploration mission.

Traditional shortest-path approaches often focus on finding the minimum geographical distance or use a predefined cost model. However, exploration vehicles are not interchangeable. They have different mobility capabilities, energy constraints, scientific instruments, and operational priorities.

For example:

- A rover with limited climbing capabilities might prioritize avoiding steep slopes.
- A rover designed for rugged terrain might tolerate rougher surfaces in exchange for a shorter route.
- A scientific expedition might accept additional traversal costs to reach geologically interesting formations.
- A mission with strict thermal constraints might prioritize areas with more favorable thermal characteristics.
- A future human exploration mission could assign significantly different importance to environmental and operational risks.

Our system makes these differences configurable rather than embedding one set of assumptions into the algorithm.

Furthermore, users can change not only the importance of individual factors but also how those factors are measured. They can select different roughness and obstacle detection methods, modify neighborhood sizes and thresholds, and define custom mathematical penalty functions.

This creates a flexible exploration planning framework rather than a route planner designed around one particular rover or mission.

## 6. Intended Impact

Our intended impact is to support more adaptable and informed planning for future robotic and potentially human exploration of Mars.

By combining planetary science datasets with customizable terrain analysis and graph-based optimization, we aim to bridge the gap between raw planetary observations and practical exploration decisions.

The platform can serve as a foundation for comparing exploration strategies, evaluating traversal trade-offs, and investigating how different vehicle capabilities and scientific priorities influence route selection.

In the longer term, the system could be extended with additional planetary datasets, more detailed rover mobility models, energy consumption estimates, communication constraints, and mission-specific safety requirements.

Ultimately, our goal is not simply to find the shortest route across Mars, but to help researchers identify the most suitable route for their particular exploration objectives.

## 7. Technologies and Tools

Our implementation combines geospatial data processing, numerical computation, backend development, interactive visualization, and graph algorithms.

**Algorithms and Computational Methods**

- Dijkstra's shortest-path algorithm for weighted-grid route optimization.
- Raster-based terrain analysis and neighborhood operations.
- Elevation-based roughness and obstacle detection.
- Weighted cost-surface construction using configurable penalty functions.

**Backend and Data Processing**

- Python for the core computational logic.
- FastAPI for exposing route planning and data-processing functionality through REST APIs.
- NumPy for numerical operations and raster-based calculations.
- Rasterio for reading, processing, and working with geospatial raster datasets.
- Geopandas for reading, processing and working with vector datasets.
- Matplotlib for data visualization.

**Frontend and Visualization**

- Interactive web-based map visualization.
- React as main framework paired with Vite.
- MapLibre GL JS for rendering geospatial data and map layers.
- Layered visualization of planetary datasets and calculated routes.

**Deployment and Infrastructure**

- Docker for application containerization.
- Docker Hub for container image distribution.
- Vercel for frontend deployment.
- Railway for backend deployment.