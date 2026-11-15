# Frontend
## Overview
Now when backend is ready i want you to implement frontend for it.

## Working dir
everything related to frontend should be in `frontend/` folder

## Backend dir 
backend file is `api.py`

## Tech stack 
React
Vite
MapLibre
everything else u need

## Inteface
### Maps
Maps should be retrieved from backend from those endpoints: `/maps/geology/vector.geojson`, `/maps/{layer}/tiles/{z}/{x}/{y}.png` etc.
All maps are reprojected and aligned.
Ability to zoom in and out of the map. (no need for resoulution change since our map is small).
### Layers
Keep interface simply, main focus should be on our maps (rendering by MapLibre), in lower left corner i want place to display current layers (map layers, backend response routes). 
Ability to hide and show layers, and change their level (move forward, backward), layers might be as raster as well as vector. 
Ability to name, rename layers, with default names enumerated like `Layer 1`, `Layer 2`, etc.

#### Map Raster Layers
Ability to inspect by click what each pixel in raster layer value correspond, and pixels center coordinates.

#### Map Vector Layers
Ability to inspect metadata of each geological/vector unit (metadata is provided in map) by click.

### Right side bar
Right side bar should be draggable/hideable.
Contains interface for defining custom parameters for route cost calculation as a nice form with default values as placeholders
and interface to choose points on the map.
#### Right side bar: custom parameters form
It essentially must provide interface for defining any customizable params, with default values as placeholders.
#### Right side bar: point choose interface
Interface to choose points/raster pixels on the map to later send to backend to perform route calculation, ability to name the points, or set default `Point 1`, `Point 2` etc names.
Ability to swap move point to the front (since the routing is sequential it matters) and to the back of the list.
Ability to remove point.
Ability to select point with "add point" button, after pressing, user must be able to point on the topest *Map* layer (Route layers should become invisible while user is choosing).
Total amount of points should not exceed 10.

### Routes layer
Each response that came from route calculation endpoint of backend should be displayed as seperate raster layer with the choosed points highlighted.
Each destination point should be inspectable on click, displaying its name and order number.
Each destination to destination route should be different colour.
Each destination to destination route should be inspectable on click, showcasing route length and cost, and folded custom params values (unfolds on click).
Ability to hide only routes, or only desinations.

### During route calculation
During route calculation map should become dim with message in the center of the screen telling to wait with custom text and
custom gif or picture of loading under it. 

### Integration 
Integrate with FastAPI backend in the `routing.py` file.
if neccessary new endpoints might be exposed to feed frontend with enough information.

### Invalid format 
If backend sends message that parameters are invlid, then maps should become dim and message in the center should pop up with exact reason of what happened.

### Success
Frontend and backend should successfull connect with each other and perform their own tasks (frontend its interface interatction, backend its calculation, validation etc) as well as intreact with each other successfully.

### Uncertain
If anything ure uncertain about design, functionality make it as user-friendly as possible.

### Note 
Backend API currently exposes API only for raster points, and since user can choose raster points and vector points its necessary to expose to API method which should take exactly same paramters as `/route` endpoint, but with difference that points can be either raster either vector, vector points should be validated and  translated to raster on the backend side with geological map .index method, after this newly exposed method and `/route` should do exactly the same thing (calculating route for raster only (cuz vector points were translated) ponts in sequential mode (from first to second, to third etc)).