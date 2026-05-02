## 4. Geometric Cleaning and Control Visualization (lab approach / scripts)

### 4.1 Role in Processing Chain

After raw vectorization, the produced geometries are not yet directly usable as final scientific results. This intermediate step has two complementary objectives:

1. stabilize geometries before topological controls,
2. provide quick visual verification of extraction quality.

In the laboratory, this post-processing layer is ensured by:

- 3_clean_noise_poly.py
- 3_clean_gapfill.py
- 6_viz_line.py
- 6_viz_poly.py

The general principle is as follows:

- clean geometric artifacts from rasterization and color thresholding,
- normalize geometric types,
- correct obvious breaks or holes,
- rasterize results again to obtain control masks and overlays.

### 4.2 Geometric Cleaning of Polygons

The 3_clean_noise_poly.py script processes polygon layers class by class. It implements a deliberately conservative geometric sanitation pipeline, designed to remove noise without excessively deforming entities.

The operations applied are as follows:

1. removal of null or empty geometries,
2. correction of invalid geometries with make_valid,
3. MultiPolygon explosion into elementary entities,
4. safety filtering on Polygon and MultiPolygon types,
5. strict verification of input CRS,
6. area calculation and filtering by minimum threshold,
7. final revalidation after cleaning.

The script explicitly imposes a workspace in EPSG:3857. This constraint is essential, since area calculation and debug raster rely on coherent metric units.

The min_area_m2 threshold plays a central role:

- it eliminates residual fragments from raster noise,
- it avoids retaining parasitic polygons in high-density graphic areas,
- it limits propagation of micro-objects in later validation phases.

Minimal excerpt (from lab/3_clean_noise_poly.py):

```py
gdf["geometry"] = gdf["geometry"].apply(
	lambda g: make_valid(g) if not g.is_valid else g
)
gdf = gdf[gdf.geometry.type.isin(["Polygon", "MultiPolygon"])]
gdf["area"] = gdf.geometry.area
gdf = gdf[gdf["area"] >= min_area_m2]
```

The script then produces two outputs per cleaned layer:

- a cleaned GeoJSON,
- a debug PNG image rasterized on the basis of the georeferenced raster.

### 4.3 Specialized Treatment of Water Class

The 3_clean_gapfill.py script applies targeted treatment on the water class. This class is particularly sensitive, as scanned cartography can introduce visual interruptions due to text, shade variations, or line breaks.

The workflow is as follows:

1. loading the water layer,
2. verification of data presence and CRS,
3. geometric union of all entities,
4. positive buffer then negative buffer to close fine gaps,
5. explicit removal of internal holes,
6. light geometric simplification,
7. rewrite of cleaned layer,
8. rasterization of result to produce control mask.

The buffer(+BUFFER_DIST) / buffer(-BUFFER_DIST) pair acts as geometric morphological closing. It allows reconnection of close segments and smoothing of fine discontinuities without manually rebuilding the layer.

Minimal excerpt (from lab/3_clean_gapfill.py):

```py
merged = unary_union(gdf.geometry)
filled = merged.buffer(BUFFER_DIST).buffer(-BUFFER_DIST)
filled = remove_holes(filled)
filled = filled.simplify(SIMPLIFY_TOL)
```

Removal of internal holes is important in a cartographic context:

- it limits false holes created by scan artifacts,
- it produces a more stable representation for pipeline continuation,
- it facilitates visual verification and cross-layer comparisons.

The script then re-exports:

- output/vect/poly/water.geojson,
- output/vect/poly/water.png.

This dual output allows simultaneous verification of vector geometry and its spatial consistency with the reference image.

### 4.4 Control Visualization of Vector Outputs

The 6_viz_poly.py and 6_viz_line.py scripts are used to produce systematic visual validation of extracted layers.

They rely on the same logic:

1. loading the semantic table legend_class_geo.csv,
2. associating each class with an integer index z,
3. reading the georeferenced raster as reference support,
4. loading all GeoJSON layers produced by vectorization,
5. rasterizing all geometries into a single class raster,
6. extraction by numpy comparison to produce masks and overlays per class.

The key optimization point is building a unique class_raster of type uint16. This choice avoids rasterizing a complete layer for each class and greatly reduces computation costs when the number of classes increases.

Then, for each class:

- an RGBA mask is generated,
- an RGB overlay is generated on the base image,
- files are exported in output/viz.

This strategy enables very rapid verification of results, class by class, without returning to an interactive GIS with each iteration.

### 4.5 Methodological Interest

This cleaning and visualization step has clear scientific value:

- it distinguishes segmentation errors from projection errors,
- it allows identification of over-segmentations or excessive cuts,
- it provides reproducible support for comparative parameter analysis,
- it allows documenting pipeline robustness before formal topological controls.

In an academic context, these outputs serve as intermediate quality proof: they are not the final result, but they show that the transformation of raster data into geometric objects has been controlled at multiple levels.

### 4.6 Conclusion

This post-processing layer remains heuristic.

- the min_area_m2 threshold must be adjusted according to scale and graphic density,
- gap filling buffer can smooth certain fine structures if too large,
- control visualization remains qualitative and does not replace formal topological validation,
- cleaning logic is still specific to certain classes, particularly water.

This step is essential: it transforms raw vectorization outputs into more stable, more legible layers better prepared for the topological validation step.

### 4.7 Figures (cleaning and gap filling)

Figure 3 - Before polygon cleaning (noise and spurious points)

<img src="images/scripts/2_before_poly_clean.png" alt="Before polygon cleaning" width="100%">

Figure 4 - After polygon cleaning

<img src="images/scripts/2_after_poly_clean.png" alt="After polygon cleaning" width="100%">

Figure 5 - Before gap filling (river with interruptions)

<img src="images/scripts/3_before_gapfill.png" alt="Before gap filling" width="100%">

Figure 6 - After gap filling

<img src="images/scripts/3_after_gapfill.png" alt="After gap filling" width="100%">

Figure 7 - Final result (without OSM)

<img src="images/scripts/4_final_result_noosm.png" alt="Final result without OSM" width="100%">

Figure 8 - Final result (with OSM)

<img src="images/scripts/4_final_result_osm.png" alt="Final result with OSM" width="100%">