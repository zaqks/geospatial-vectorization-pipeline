## 4. Topological Validation (lab approach / scripts)

### 4.1 Objective

Topological validation aims to detect geometric and semantic inconsistencies in produced vector layers. It occurs after vectorization, geometric cleaning, and control visualization phases. The main script is 7_validation_topo.py.

The approach adopted is validation through intersection rules between classes.

### 4.2 Control Strategy

The script loads multiple layers (lines and polygons), applies basic cleaning (valid, non-empty geometries), then executes spatial tests via spatial indexing.

Central function:

- find_intersections(a, b)

This function:

1. builds spatial index of layer b,
2. searches candidates by extent (bounding boxes),
3. tests exact geometric intersection,
4. collects conflicting geometries.

### 4.3 Implemented Validation Rules

Explicit checks in the script cover notably:

- buildings intersecting water,
- buildings intersecting road network,
- inconsistencies between road hierarchies,
- residential zones intersecting water,
- metro conflicts vs buildings / water.

The script then exports error layers as GeoJSON (errors_*.geojson) for cartographic audit.

These conflicts are not only detected: they also serve as basis for a cleaning and contextual resolution phase. The idea is to retain the most relevant class according to cartographic context. For example, in case of overlap between a road and a building, priority is given to the road and the building geometry is adjusted or removed in the conflict zone.

### 4.4 Methodological Interest

This approach enables:

- reproducible and scriptable validation,
- clear separation between detection and correction,
- easy exploitation of errors in a GIS for expert review.

In an academic context, this formalizes business constraints as calculable rules.

### 4.5 Lab Section Conclusion

The laboratory work provides a complete foundation:

- raster extraction and legend,
- georeferencing,
- multi-geometry vectorization,
- cleaning,
- control visualization,
- beginning of topological validation.

The main value of this phase is having transformed exploratory work into reusable algorithmic building blocks for the pipeline version.
