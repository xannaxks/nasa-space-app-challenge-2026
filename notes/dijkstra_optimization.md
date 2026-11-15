# Main

The current Dijkstra implementation and sequential path-building algorithm, used to find the least-cost distance between two raster pixels and construct a complete route, are too slow. Even finding the shortest path between two points takes nearly 20 seconds. We need to optimize the implementation.

## Algorithm-Level Optimizations

### Early Termination
Terminate the search as soon as the destination node is extracted from the priority queue.

## Data Structures and Implementation-Level Optimizations

### Flat Indexing
Represent each raster cell using a single integer node identifier instead of coordinate tuples. Convert between flat indices and `(x, y)` coordinates only when necessary.

Avoid unnecessary tuple creation, particularly inside performance-critical loops.

### Arrays Over Objects
Prefer NumPy arrays and primitive data types over custom classes and their instances wherever possible.

### Priority Queue
Use Python's built-in `heapq` implementation for the priority queue.

### Precomputation
Precompute values wherever applicable to avoid repeated calculations during pathfinding, while keeping memory consumption under control.

## Annotations and logging
Please put commentary annotations of what some confusing lines are doing and logging into console.