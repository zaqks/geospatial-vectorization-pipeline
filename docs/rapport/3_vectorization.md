## 3. Vectorization and Post-Processing (lab approach / scripts)

### 3.1 General Principle

Vectorization transforms raster patterns into semantically classified geometric objects (LineString, Polygon). In the laboratory, this phase is distributed across several scripts:

- 2_vectorization_line.py
- 2_vectorization_dotted.py
- 2_vectorization_poly.py
- 3_clean_noise_poly.py
- 3_clean_gapfill.py

The class reference is provided by data/legend_class_geo.csv.

### 3.2 Polygon Vectorization

The 2_vectorization_poly.py script follows exact RGB classification logic:

1. reading the georeferenced raster,
2. building a color -> class table,
3. encoding pixels (RGB -> class index),
4. extracting shapes via rasterio.features.shapes,
5. generating GeoJSON per class.

Technical points:

- processing on 3 RGB bands,
- unmatched classes ignored (label = -1),
- export per class in output/vect/poly.

This choice is efficient when the source map uses stable flat colors.

### 3.3 Continuous Line Vectorization

The 2_vectorization_line.py script handles linear classes except railway:

1. color masking with tolerance,
2. morphological closing to reconnect minor breaks,
3. removal of too-small objects (threshold in m2 converted to pixels),
4. skeletonization (medial axis),
5. conversion to linear geometries,
6. simplification and filtering by minimum length.

Structuring parameters:

- COLOR_TOLERANCE,
- CLOSING_RADIUS,
- MIN_OBJECT_SIZE_M2,
- MIN_LINE_LENGTH,
- SIMPLIFY_TOLERANCE.

These parameters control the precision/robustness trade-off.

### 3.4 Dotted Line Vectorization (railway)

The 2_vectorization_dotted.py script explicitly addresses the railway class, which is harder to extract:

- color interval masking (lower/upper bound),
- morphological opening + closing (denoising and bridging),
- skeletonization,
- endpoint detection,
- reconnection of close endpoints via KDTree,
- linear GeoJSON export.

This method is adapted for discontinuous graphs and dotted symbols.

### 3.5 Geometric Cleaning of Polygons

The 3_clean_noise_poly.py script applies a sanitation pipeline:

- removal of null/empty geometries,
- geometric validity correction (make_valid),
- MultiPolygon explosion,
- filtering on geometric type,
- elimination of small areas.

Objective:

- remove artifacts from raster noise,
- maintain a more stable geometric schema for analysis.

### 3.6 Targeted Gap Filling on Water Class

The 3_clean_gapfill.py script performs specialized treatment on water:

1. union of objects,
2. positive buffer then negative buffer (closing fine gaps),
3. removal of internal holes,
4. geometric simplification,
5. re-export of water layer.

This treatment corrects voids created by map text or shade interruptions.

### 3.7 Control Visualization (visual validation step)

The 6_viz_line.py and 6_viz_poly.py scripts rasterize all classes and produce:

- RGBA masks per class,
- overlays on base image.

A notable optimization is already present:

- unique class raster (uint16) then extraction of each mask by numpy comparison.

### 3.8 Vectorial Outputs

Main directory:

- output/vect/poly/*.geojson
- output/vect/line/*.geojson

Supplementary outputs:

- PNG debug/overlay for qualitative inspection.

These outputs are then taken up by the cleaning and control visualization step, documented in the next chapter, before entering topological validation.

### 3.9 Conclusion

- sensitivity to chromatic collisions between classes,
- risk of edge over-segmentation,
- cleaning still heuristic (parameters to calibrate per zone and cartographic style),
- color-based methods not robust to map style changes.

The lab chain is mature enough to produce an exploitable and robust database for subsequent topological controls.
