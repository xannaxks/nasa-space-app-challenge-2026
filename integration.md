# Integration
## Overview
Now when we have workflow for traverse cost calculating and minimal route with Dijkstra, and backend with custom parameters validation, i want to integrate them together into one backend system.

## On startup
On startup backend should load the maps from `aligned/`

## Main Endpoints
One main REST endpoint accepts customizable parameters (which is already done) plus raster coordinates (pixel coordinates), amount under or equal 20. Task to build workflow where customizable parameters are validated with fallback to default values (already done), and build shortest path from each point to each (one to one), then use those each per each shortest paths to build complete route from first to last cell, use simply nearest for current cell greedy approach, no need for full backtracking and returns this full route (from first cell to last) back as response to render it further on frotend. 

## Map endpoints
Endpoints that return maps data, maps such as:
dtm elevation - `aligned\DTM_CTX_mosaic_MTM100m_norm01.tif`
slope degree - `aligned\DTM_slope_deg_MTM100m.tif`
Geological units - `aligned\GeoUnits_MTM100m.tif`
IR day - `aligned\THEMIS_Day_MTM100m_norm01.tif`
IR night - `aligned\THEMIS_Night_MTM100m_norm01.tif`
Slope degree - `aligned\DTM_slope_deg_MTM100m.tif`
Hillshade - `aligned\DTM_hillshade_MTM100m.tif`

Those endpoints will be access by frontend to render them in browser further.

## Invalid parameters
In case of invalid parameters returns message with explanation.

## Limiters
### REST endpoint limiter
Put a slowapi rate limiter by IP address with rate 20 requests per minute with data storing into local memory (not Redis, just local RAM memory). 
Put active http connections limiter by no more then 50 active http connections at the same time.

## End
At the backends end of lifetime, it should clear all the limiter data stored in memory, close all the opened and don't leave anything opened.