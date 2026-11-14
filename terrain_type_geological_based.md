i want u to define the terrain type penalty based on geological unit type, it gonna be dictionary where each value from 1 to 14 equals to some penalty score (provided by user, so u need to make it custom parameter and include into schemas, pyndatic etc). For the description i want u to put this annotation, so users understand what geological unit they wanna penalty more:
1 - Eolian bedform unit
2 - Nili planum fan unit
3 - Jezero fan 1 unit
4 - Jezero fan 2 unit
5 - Jezero floor unit
6 - Lower etched unit
7 - Nili planum 1 unit
8 - Nili planum 2 unit
9 - Rugged bright unit
10 - Upper etched unit
11 - Crater ejecta unit
12 - Crater interior unit
13 - Crater rim unit
14 - Smooth unit

User should use either this "Terrain type penalty based on geological map" or "Terrain type penalty based on IR swing map", but still can use both, but put warning that its not basically supposed to mix two of them, and recommenede to choose one.

There is already dictionary for it, but its empty right now in file `routing.py`: `terrain_type_geological_based_dict: Dict[int, float] = {}`
And method for its penalty already for it in file `routing.py`: `def get_terrain_type_geological_based_cost(maps: RasterMaps, cell: Tuple[int, int]) -> float:`

The penalty for this shouldnt use math functions like others, rather take penalty coefficients for each geological unit.

Make sure to intergate this with whole system (validation, post request, dijkstra etc)
Dont forget adding field to choose what map use to define terrain type: IR swing, Geological units, or Both (as noticed both shouldn't be recommend, rather choosed one of them, but option to take both should remain and work properly)

Put reasonable default values for it, and mark IR swing based terrain type as default.