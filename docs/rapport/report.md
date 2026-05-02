## 1. Data Acquisition (scripts)

### 1.1 Step Objective

The goal of this phase is to download a scanned map covering the target municipality with enough detail to support color-based vectorization. In the lab folder, this step is mainly implemented by:

- 0_data.py
- 0_legend_extract.py
- 0_legend_overlay_poly.py
- 0_legend_overlay_line.py

This phase has two parts:

1. spatial acquisition (downloading and assembling raster tiles),
2. semantic acquisition (building the legend table and visually verifying classes).

### 1.2 Spatial Delimitation of the Study Area

The 0_data.py script uses Nominatim (via geopy) to geocode the municipality "El Harrach, Algeria" and automatically retrieve a bounding box (south, north, west, east).

Assumptions retained in the lab:

- the Nominatim bounding box is sufficiently close to the useful extent,
- padding is added to avoid cutting features at the edges of the zone.

Important technical parameters:

- ZOOM = 18
- TILE_SIZE = 256
- padding = 1

Zoom level z18 provides detailed resolution, with a trade-off between precision and data volume.

### 1.3 Geographic to Tile Grid Conversion

The script implements:

- latlon_to_tile(lat, lon, zoom)
- tile_to_latlon(x, y, zoom)

These functions ensure conversion between:

- geographic coordinates (WGS84, lat/lon),
- web tile indices (x, y, z) in Web Mercator projection.

This conversion is fundamental for knowing exactly which tiles to download and for calculating the actual extent of the mosaicked image.

Minimal excerpt (from lab/0_data.py):

```py
def latlon_to_tile(lat, lon, zoom):
	lat_rad = math.radians(lat)
	n = 2.0**zoom
	x = int((lon + 180.0) / 360.0 * n)
	y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
	return x, y
```

### 1.4 Downloading, Local Cache, and Assembly

Tiles are retrieved from Carto basemaps (voyager_nolabels style) and stored in a local cache:

- data/tiles/18/x_y.png

The cache allows:

- test reproducibility,
- reduced network requests,
- faster reruns of the experimental pipeline.

Minimal excerpt (cache + downloading):

```py
tile_path = f"{cache_dir}/{x}_{y}.png"
if os.path.exists(tile_path):
	tiles[(x, y)] = Image.open(tile_path).convert("RGB")
else:
	r = requests.get(url, headers=headers, timeout=10)
```

After downloading, the tiles are stitched into a single image:

- output: data/el_harrach_highres_map.png

The script also calculates the final extent of the mosaic (north/south/west/east), which facilitates geometric verification before georeferencing.

### 1.5 Color Signature Extraction

The 0_legend_extract.py script performs color analysis of the full image:

- reading the RGB image,
- flattening pixels,
- aggregating occurrences by triplet (r, g, b) with Polars,
- calculating appearance percentages,
- exporting dominant classes to data/legend.csv.

Threshold applied in the export:

- only colors >= 0.1% are retained.

Why this step matters:

- identify dominant hues before segmentation,
- detect rare or noisy classes,
- prepare a class reference usable in vectorization scripts.

### 1.6 Visual Verification of the Legend

The overlay scripts (0_legend_overlay_poly.py, 0_legend_overlay_line.py) apply color masking by class from legend_class_geo.csv.

Principle:

1. hex to BGR conversion,
2. detection of target pixels with tolerance (often 1),
3. generation of a control image where detected pixels are painted red,
4. export class by class in output/overlays.

For lines, morphological preprocessing (closing and dilation) is added to make fine linear patterns visually legible.

### 1.7 Outputs and Artifacts of the Acquisition Phase

Main products:

- base raster: data/el_harrach_highres_map.png
- table of dominant colors: data/legend.csv
- business class table: data/legend_class_geo.csv (with geometry and z-index columns added)
- control overlays: output/overlays/poly/*.png and output/overlays/line/*.png

These artifacts directly feed the next steps (georeferencing and vectorization).

### 1.8 Conclusion

- dependence on the quality of the source colors (compression, aliasing, local variations),
- strong sensitivity of masking to the chosen tolerance,
- risk of confusion between chromatically close classes,
- extraction of semantic classes remains semi-supervised (legend table maintained manually).

Despite these limitations, the acquisition phase provides a robust experimental basis for the subsequent geospatial chain.

### 1.9 Figures (script captures)

Figure 1 - High-resolution map download (input)

<img src="images/scripts/0_input.png" alt="High resolution map download" width="100%">

## 2. Georeferencing (scripts)

### 2.1 Scientific and Technical Challenge

Georeferencing converts a raster image made of pixels into a spatially usable layer in a GIS. In the laboratory, this operation is performed by the 1_georef.py script.

Concrete objective:

* produce a georeferenced GeoTIFF from the mosaicked image,
* guarantee projection consistency with subsequent vectorization processes.

### 2.2 Inputs

Main inputs:

* source image: data/el_harrach_highres_map.png
* geographic bounding box (lat/lon) of the target area, obtained upstream through a geocoding service

Control points used:

* top-left corner of the bounding box,
* bottom-right corner of the bounding box

These two points come from ground-truth data returned by the geocoding service and correspond to real coordinates, not hypothetical ones. The bounding box is precise enough to define the spatial extent of the image exactly.

Since the area is represented by a strictly rectangular extent, these two points are sufficient to reconstruct the whole transformation. Using four points would make no difference in the final result, since the remaining corners are mathematically derived from the same bounding box.

* the stitched image is already aligned without complex local deformation,
* an affine transformation is sufficient to move from image space to geographic space,
* the provided bounding box is perfectly consistent with the image (exact alignment with no offset).

### 2.3 Spatial Reference System

The script applies an explicit conversion to Web Mercator (EPSG:3857):

1. longitude conversion -> metric X,
2. latitude conversion -> metric Y,
3. construction of metric extent [min_x, min_y, max_x, max_y].

Formulation used (Earth radius R = 6378137):

$$
X = R \cdot \text{rad}(\lambda), \quad
Y = R \cdot \ln\left(\tan\left(\frac{\pi}{4} + \frac{\text{rad}(\varphi)}{2}\right)\right)
$$

The EPSG:3857 choice is consistent with the web origin of raster tiles.

### 2.4 Construction of the Affine Transform

The transform is calculated via rasterio.from_bounds from:

* metric bounds derived from the bounding box,
* the actual width and height of the image.

The two control points (top-left and bottom-right) fully and uniquely define this extent. In this case, they are sufficient and equivalent to a four-point configuration, since the geometry is strictly rectangular and perfectly defined by the ground bounding box.

The affine transformation is derived directly, ensuring correspondence:

* pixel (0, 0) -> top-left corner,
* pixel (width, height) -> bottom-right corner.

This operation ties each pixel (column, row) to a continuous projected coordinate.

Minimal excerpt (from lab/1_georef.py):

```py
transform = from_bounds(
	min_x, min_y,
	max_x, max_y,
	width, height
)
```

### 2.5 Writing an Optimized GeoTIFF

The script writes data/el_harrach_georef.tif with the following options:

* GTiff driver,
* 3 RGB bands,
* crs = EPSG:3857,
* DEFLATE compression,
* predictor = 2,
* internal tiling 256x256.

These parameters reduce disk size and speed up windowed reads during segmentation/vectorization steps.

Minimal excerpt (GeoTIFF writing):

```py
with rasterio.open(output_tif, "w", driver="GTiff", crs="EPSG:3857", transform=transform) as dst:
	dst.write(img_np[:, :, 0], 1)
	dst.write(img_np[:, :, 1], 2)
	dst.write(img_np[:, :, 2], 3)
```

### 2.6 Validation Performed in the Lab

Typical checks:

* opening the GeoTIFF in QGIS/ArcGIS,
* visual alignment check with reference basemaps,
* verification of CRS and extent metadata.

The conversion to EPSG:3857 is then imposed as a precondition in several downstream scripts (vectorization, cleaning, visualization).

### 2.7 Outputs and Impact on the Experimental Pipeline

Main output:

* data/el_harrach_georef.tif

This file becomes the single input to the vectorization chain:

* extraction of polygon classes,
* extraction of linear classes,
* geometric cleaning,
* visualization mask production.

### 2.8 Conclusion

* precision depends directly on the quality of the input bounding box, based on reliable ground data,
* two control points (opposite corners) are sufficient because the extent is strictly rectangular and perfectly known,
* the result obtained is equivalent to a four-point configuration in this specific case,
* approximation inherent to the Mercator projection (area distortions),
* the absence of additional ground control points (GCPs) does not affect overall precision in this context.

### 2.9 QGIS Verification Figure

Figure 2 - First verification of vectorization and georeferencing in QGIS

<img src="images/scripts/1_qgis_georef_check_poly.png" alt="QGIS georef and vectorization verification" width="100%">

## 3. Vectorization and Post-Processing (scripts)

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

### 3.6 Targeted Gap Filling on the Water Class

The 3_clean_gapfill.py script performs specialized treatment on water:

1. union of objects,
2. positive buffer then negative buffer (closing fine gaps),
3. removal of internal holes,
4. geometric simplification,
5. re-export of the water layer.

This treatment corrects voids created by map text or shading interruptions.

### 3.7 Control Visualization (visual validation step)

The 6_viz_line.py and 6_viz_poly.py scripts rasterize all classes and produce:

- RGBA masks per class,
- overlays on the base image.

A notable optimization is already present:

- a unique class raster (uint16) followed by extraction of each mask by numpy comparison.

### 3.8 Vector Outputs

Main directory:

- output/vect/poly/*.geojson
- output/vect/line/*.geojson

Supplementary outputs:

- PNG debug/overlay for qualitative inspection.

These outputs are then taken up by the cleaning and control visualization step, documented in the next chapter, before topological validation.

### 3.9 Conclusion

- sensitivity to chromatic collisions between classes,
- risk of edge over-segmentation,
- cleaning remains heuristic (parameters must be calibrated per zone and cartographic style),
- color-based methods are not robust to map style changes.

The lab chain is mature enough to produce an exploitable and robust database for subsequent topological checks.

## 4. Geometric Cleaning and Control Visualization (scripts)

### 4.1 Role in the Processing Chain

After raw vectorization, the produced geometries are not yet directly usable as final scientific results. This intermediate step has two complementary objectives:

1. stabilize geometries before topological checks,
2. provide quick visual verification of extraction quality.

In the laboratory, this post-processing layer is handled by:

- 3_clean_noise_poly.py
- 3_clean_gapfill.py
- 6_viz_line.py
- 6_viz_poly.py

The general principle is as follows:

- clean geometric artifacts from rasterization and color thresholding,
- normalize geometric types,
- correct obvious breaks or holes,
- rasterize the results again to obtain control masks and overlays.

### 4.2 Geometric Cleaning of Polygons

The 3_clean_noise_poly.py script processes polygon layers class by class. It implements a deliberately conservative geometric sanitation pipeline, designed to remove noise without excessively deforming the entities.

The operations applied are as follows:

1. removal of null or empty geometries,
2. correction of invalid geometries with make_valid,
3. MultiPolygon explosion into elementary entities,
4. safety filtering on Polygon and MultiPolygon types,
5. strict verification of the input CRS,
6. area calculation and filtering by minimum threshold,
7. final revalidation after cleaning.

The script explicitly imposes a workspace in EPSG:3857. This constraint is essential, since area calculation and debug rasterization rely on coherent metric units.

The min_area_m2 threshold plays a central role:

- it eliminates residual fragments from raster noise,
- it avoids retaining parasitic polygons in high-density graphic areas,
- it limits the propagation of micro-objects in later validation phases.

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
- a debug PNG image rasterized from the georeferenced raster.

### 4.3 Specialized Treatment of the Water Class

The 3_clean_gapfill.py script applies targeted treatment to the water class. This class is particularly sensitive, as scanned cartography can introduce visual interruptions due to text, shading variations, or line breaks.

The workflow is as follows:

1. loading the water layer,
2. verification of data presence and CRS,
3. geometric union of all entities,
4. positive buffer then negative buffer to close fine gaps,
5. explicit removal of internal holes,
6. light geometric simplification,
7. rewrite of the cleaned layer,
8. rasterization of the result to produce a control mask.

The buffer(+BUFFER_DIST) / buffer(-BUFFER_DIST) pair acts as geometric morphological closing. It allows reconnection of close segments and smoothing of fine discontinuities without manually rebuilding the layer.

Minimal excerpt (from lab/3_clean_gapfill.py):

```py
merged = unary_union(gdf.geometry)
filled = merged.buffer(BUFFER_DIST).buffer(-BUFFER_DIST)
filled = remove_holes(filled)
filled = filled.simplify(SIMPLIFY_TOL)
```

Removing internal holes is important in a cartographic context:

- it limits false holes created by scan artifacts,
- it produces a more stable representation for pipeline continuation,
- it facilitates visual verification and cross-layer comparisons.

The script then re-exports:

- output/vect/poly/water.geojson,
- output/vect/poly/water.png.

This dual output allows simultaneous verification of the vector geometry and its spatial consistency with the reference image.

### 4.4 Control Visualization of Vector Outputs

The 6_viz_poly.py and 6_viz_line.py scripts are used to produce systematic visual validation of the extracted layers.

They rely on the same logic:

1. loading the semantic table legend_class_geo.csv,
2. associating each class with an integer index z,
3. reading the georeferenced raster as reference support,
4. loading all GeoJSON layers produced by vectorization,
5. rasterizing all geometries into a single class raster,
6. extracting by numpy comparison to produce masks and overlays per class.

The key optimization point is building a unique class_raster of type uint16. This choice avoids rasterizing a complete layer for each class and greatly reduces computation costs when the number of classes increases.

Then, for each class:

- an RGBA mask is generated,
- an RGB overlay is generated on the base image,
- files are exported in output/viz.

This strategy enables very rapid verification of results, class by class, without returning to an interactive GIS for each iteration.

### 4.5 Methodological Interest

This cleaning and visualization step has clear scientific value:

- it distinguishes segmentation errors from projection errors,
- it allows identification of over-segmentations or excessive cuts,
- it provides reproducible support for comparative parameter analysis,
- it documents pipeline robustness before formal topological checks.

In an academic context, these outputs serve as intermediate quality evidence: they are not the final result, but they show that the transformation of raster data into geometric objects has been controlled at multiple levels.

### 4.6 Conclusion

This post-processing layer remains heuristic.

- the min_area_m2 threshold must be adjusted according to scale and graphic density,
- the gap-filling buffer can smooth certain fine structures if it is too large,
- control visualization remains qualitative and does not replace formal topological validation,
- cleaning logic is still specific to certain classes, particularly water.

This step is essential: it transforms raw vectorization outputs into more stable, more legible layers that are better prepared for the topological validation step.

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

## 4. Topological Validation (scripts)

### 4.1 Objective

Topological validation aims to detect geometric and semantic inconsistencies in the produced vector layers. It occurs after the vectorization, geometric cleaning, and control visualization phases. The main script is 7_validation_topo.py.

The adopted approach is validation through intersection rules between classes.

### 4.2 Control Strategy

The script loads multiple layers (lines and polygons), applies basic cleaning (valid, non-empty geometries), then executes spatial tests via spatial indexing.

Central function:

- find_intersections(a, b)

This function:

1. builds a spatial index of layer b,
2. searches candidates by extent (bounding boxes),
3. tests exact geometric intersection,
4. collects conflicting geometries.

### 4.3 Implemented Validation Rules

Explicit checks in the script notably cover:

- buildings intersecting water,
- buildings intersecting the road network,
- inconsistencies between road hierarchies,
- residential zones intersecting water,
- metro conflicts versus buildings / water.

The script then exports error layers as GeoJSON (errors_*.geojson) for cartographic audit.

These conflicts are not only detected: they also serve as the basis for a cleaning and contextual resolution phase. The idea is to retain the most relevant class according to cartographic context. For example, in the case of overlap between a road and a building, priority is given to the road and the building geometry is adjusted or removed in the conflict zone.

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

The main value of this phase is that it transforms exploratory work into reusable algorithmic building blocks for the pipeline version.

## Industrialized Pipeline: From Lab Prototype to Flow Orchestration

### 1. General Positioning

In the laboratory prototype, each step of geospatial processing was first expressed as autonomous scripts: acquisition, georeferencing, vectorization, cleaning, visualization, and topological validation. The pipeline version follows exactly this functional logic, but transforms it into a suite of triggerable, observable flows deployed in infrastructure separate from the input frontend.

This change is significant from a methodological standpoint. We are no longer dealing with a simple local processing tool, but with a distributed computing system where:

- the frontend only collects user inputs and presents progress status,
- the API plays the control-plane role,
- the pipeline carries heavy geospatial computation,
- PostgreSQL maintains metadata and job state,
- Hugging Face serves as the object bucket for large files,
- GitHub Actions automates deployment to HF Spaces.

This separation is that of a data-oriented architecture. It is more suitable than a classical monolithic application, because the main load is not CRUD logic, but manipulation of rasters, GeoJSON, PNG masks, and large variable-sized artifacts.

### 2. From Script to Flow

The transition from lab to pipeline does not consist of rewriting the geospatial logic. It consists of encapsulating it within more robust execution boundaries.

In the lab directory, scripts serve as scientific prototypes:

- 1_georef.py for georeferencing,
- 2_vectorization_*.py for segmentation and vector extraction,
- 3_clean_*.py for geometric cleaning and gap filling,
- 6_viz_*.py for control visualization,
- 7_validation_topo.py for topological validation rules.

In services/pipeline, these steps become Plombery flows. The business logic remains close, but execution is recomposed around several technical properties:

- atomic and chainable steps,
- progress published at each subtask,
- easier recovery in case of failure,
- workspace isolated by UUID,
- data exchange via temporary local files rather than shared memory.

The pipeline thus behaves as a state machine for geospatial processing rather than a simple single function.

### 3. Overall System Architecture

The complete system rests on three application services and two infrastructure layers.

The Vite frontend, in services/app, provides the input and consultation interface. It receives a file, a bounding box with two points, and then opens an SSE stream to track execution.

The FastAPI API, in services/api, receives the upload, validates the input structure, persists metadata, sends the image to Hugging Face, then triggers the pipeline via an HTTP call to the compute service.

The pipeline, in services/pipeline, executes heavy geospatial transformations in a pangeo/pangeo-notebook:6f9fda2 container, which natively provides Python 3.12, GDAL, GEOS, and the necessary geospatial components.

PostgreSQL stores the following relational objects:

- inputs for user inputs and progress,
- outputs for the 1-1 link with input,
- output_files for exported artifacts,
- overlay_images for visualization masks.

Hugging Face serves as external object storage. Large files are not copied as blobs into the database, but as bucket/repository-style paths. This approach greatly reduces SQL transaction size and allows artifacts to be moved without overloading PostgreSQL.

### 4. Ingestion and Control on the API Side

The application entry point is POST /api/upload.

The frontend sends a multipart form containing:

- the image file,
- the bounding box serialized as {"points":[{"lat":... ,"lng":...},{"lat":... ,"lng":...}]}.

The API applies several control steps:

- JSON structure validation,
- conversion of points into four numeric bounds,
- job UUID generation,
- image transfer to the Hugging Face bucket,
- creation of an Input row in the database with initial progress at 0.

The API does not directly launch geospatial processes. It serves as a transactional gateway between the user world and the compute layer. Once the upload is persisted, it calls trigger_pipeline_with_retry, which contacts the first pipeline flow with a retry policy and timeout. This point is essential: if the pipeline takes a few seconds to start or if the service is momentarily unavailable, the frontend does not block waiting for synchronous computation.

This logic transforms a classic web request into an asynchronous task processed out of band.

### 5. Real-Time Channel and Execution Return

Progress consultation is done via Server-Sent Events.

The frontend opens GET /api/events/{uuid} right after sending the upload. The backend first returns a snapshot from the database, then relays events published by the pipeline via POST /api/events/notify.

This mechanism addresses two needs:

- give immediate feedback to the user,
- avoid aggressive polling on the API.

As output, GET /api/result/{uuid} assembles the preview URL, the list of overlays, and the list of exported files. The frontend can then display the final result and maintain certain local states to accelerate subsequent requests.

In this architecture, SSE plays the role of a lightweight progress bus. It does not replace persistence, but complements it with a real-time UX layer.

### 6. Hugging Face Object Storage and PostgreSQL Role

The system makes a strict separation between metadata and payloads.

PostgreSQL carries transactional control:

- job UUID,
- file name,
- storage ref,
- geographic bounds,
- progress percentage,
- relations between input, exports, and overlays.

Hugging Face carries files:

- uploaded input image,
- exported GeoJSON,
- output.zip archive,
- visualization images,
- PNG masks.

The storage path is derived from the UUID, giving a stable and predictable structure of the form uploads/<uuid>/input/<name>. The default bucket is configured by HF_BUCKET_REPO_ID and the connection relies on HF_TOKEN.

This design is more robust than storing everything in the database for three reasons:

- it avoids burdening tables with large binaries,
- it allows artifacts to be versioned or migrated as independent objects,
- it facilitates sharing between the API and pipeline without duplicating serialization logic.

### 7. Compute Flows and Correspondence with Lab Scripts

The pipeline follows the scientific sequence of the laboratory, but makes it executable and reproducible in a server environment.

#### 7.1 Flow 0: Workspace Preparation

0_setup_workspace initializes an isolated workspace under /tmp/<uuid>.

Its responsibilities are as follows:

- create the local compute directory structure,
- retrieve the image from Hugging Face using Input.image_ref,
- convert it back to a local working PNG,
- copy the business configuration files legend_class_geo.csv and colors.csv,
- notify the backend of initial progress,
- chain to georeferencing.

This step is the hinge between the control plane and the data plane. It guarantees that each job has its own workspace and that the following flows do not depend on shared global states.

#### 7.2 Flow 1: Georeferencing

The georeferencing flow transforms the raw image into a spatially coherent GeoTIFF.

It retrieves bounds stored in the database, orders them correctly, then builds an affine transformation starting from the user bbox. The raster is written with internal compression and tiling to reduce disk size and optimize partial reads.

The result of this flow becomes the common reference for all following steps. From this point on, the image is no longer just a document, but a georeferenced raster usable as geospatial support.

#### 7.3 Flow 2: Vectorization

Vectorization is decomposed into multiple specialized flows by object type:

- continuous lines,
- dotted lines,
- polygons.

This decomposition directly corresponds to the laboratory prototype scripts, but with orchestrable execution and finer progress reporting.

The general principle remains the same as in the experimental scripts:

- color classification,
- morphological cleaning,
- component extraction,
- geometric simplification,
- GeoJSON export.

This phase concentrates most of the compute load. That is why it is isolated in the pipeline and should not run in a simple synchronous API layer.

#### 7.4 Flow 3: Geometric Cleaning and Gap Filling

The lab cleaning scripts have been retained as reference logic and transformed into dedicated pipeline steps.

Cleaning plays a dual role:

- remove geometric noise from segmentation,
- stabilize entities before visualization and validation.

The polygon layer notably applies:

- correction of invalid geometries,
- removal of empty entities,
- filtering by minimum area,
- revalidation after cleaning.

The water class is a special case, as it benefits from gap-filling treatment via positive then negative buffer operations to close fine gaps and produce more continuous geometry.

In a data-intensive architecture, this step is important: it reduces false positives visible in later validation and limits manual corrections.

#### 7.5 Flow 4: Control Visualization

Visualization scripts do not only serve to produce attractive figures. They constitute a reproducible QA mechanism.

The idea is to rasterize vector outputs in a unique class space, then generate for each class:

- a mask,
- an overlay on the reference image,
- a PNG output in the viz folder.

This approach makes it very fast to check whether a class was extracted correctly, whether it is shifted, over-segmented, or missing. Technically, generating a unique class raster limits computation costs compared with rasterizing each layer independently.

In the pipeline, this step connects the scientific reading of outputs with operational visual feedback. It is therefore both an analysis tool and a debugging tool.

#### 7.6 Flow 5: Final Export

The last flow archives the outputs, pushes them to the object bucket, and updates the final state in the database.

The export typically produces:

- an output.zip archive,
- the GeoJSON files,
- the PNG overlays,
- persistent references in output_files and overlay_images.

Progress reaches 100%, and the API can then serve a complete result to the frontend.

### 8. Topological Validation and Its Place in the Pipeline

Topological validation is documented in the laboratory by the 7_validation_topo.py script, but the current pipeline version focuses first on execution robustness and data transport quality.

The industrialized pipeline already integrates useful pre-checks:

- correction of invalid geometries,
- removal of parasitic artifacts,
- CRS consistency,
- intermediate visualization for human review.

The actual business topological validation remains an additional level. In a target architecture, it comes after cleaning and before final export, with rules for semantic conflicts, intersections, and spatial relationships.

This distinction is important for the report: the pipeline does not ignore validation, but places it correctly. The pre-validation steps already reduce the risk of errors, while a full topological validation can be added as a dedicated flow without changing the overall architecture.

### 9. GitHub Actions and Deployment to Hugging Face Spaces

The project uses GitHub Actions to synchronize the services to Hugging Face Spaces.

Two main workflows exist:

- one workflow for services/api, triggered on push to main and on manual execution,
- one workflow for services/pipeline, triggered on the same principle.

Their logic is simple but effective:

1. checkout the repository,
2. initialize a git repository in the target folder,
3. configure the CI git identity,
4. add the Hugging Face remote,
5. commit the changes,
6. force push to the target Space.

This mechanism is well suited to a project of this type because it allows a demo version or a production prototype to be delivered quickly, without maintaining a complex build chain for each service.

### 10. Infrastructure, HPC, and Big Data

The infrastructure is intentionally split to support large data.

The pipeline runs in a container based on pangeo/pangeo-notebook, which provides a richer geospatial stack than a minimal Python image. The docker-compose.yml also sets a memory limit for the pipeline service, making behavior more predictable when multiple jobs or layers are processed.

This architecture is suited to intensive processing for several reasons:

- geospatial computation is isolated in a specialized service,
- the web layer does not carry the CPU load,
- intermediate artifacts are written locally in a UUID-based workspace,
- results are exported outside the database,
- progress updates are published without blocking execution.

From a big-data perspective, the most important point is the separation between orchestration and computation. The API only routes, persists, and signals. The pipeline handles the heavy operations on rasters, vectors, and masks. This separation then makes it easier to evolve toward finer-grained parallelism or a multi-worker architecture.

### 11. Conclusion

The pipeline version is not a simple duplication of the lab code. It is the transformation of a set of local experiments into a reproducible, observable, and deployable computation architecture. The scripts provided the geospatial logic; the flows give it a systemic form.

The result is a clear separation of responsibilities:

- the frontend collects and displays,
- the API controls and persists,
- the pipeline computes,
- PostgreSQL tracks,
- Hugging Face stores,
- GitHub Actions deploys.

This decomposition is exactly what is needed for data-intensive geospatial processing.

### 12. Figures (web application and pipeline dashboard)

Figure 9 - Home screen of the web application

<img src="images/app_and_stuff/1_home.png" alt="Home screen webapp" width="100%">

Figure 10 - User input section

<img src="images/app_and_stuff/1_home_input.png" alt="User input section" width="100%">

Figure 11 - Vectorization result (view 1)

<img src="images/app_and_stuff/3_result_1.png" alt="Vectorization result" width="100%">

Figure 12 - Zoomed vectorization result (view 2)

<img src="images/app_and_stuff/3_result_2.png" alt="Zoomed vectorization result" width="100%">

Figure 13 - Pipeline dashboard capture

<img src="images/app_and_stuff/4_pipeline_dashbaord.png" alt="Dashboard pipeline" width="100%">
