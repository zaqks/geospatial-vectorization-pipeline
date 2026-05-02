## 2. Georeferencing (lab approach / scripts)

### 2.1 Scientific and Technical Challenge

Georeferencing converts a "pixel" raster image into a spatially usable layer in a GIS. In the laboratory, this operation is performed by the `1_georef.py` script.

Concrete objective:

* produce a georeferenced GeoTIFF from the mosaicked image,
* guarantee projection consistency with subsequent vectorization processes.

### 2.2 Inputs

Main inputs:

* source image: `data/el_harrach_highres_map.png`
* geographic bounding box (lat/lon) of the target area, obtained via geocoding service upstream

Control points used:

* top-left corner of the bounding box,
* bottom-right corner of the bounding box

These two points come from ground truth data from the geocoding service and correspond to real coordinates, not hypothetical ones. The bounding box is precise enough to define exactly the spatial extent of the image.

Since the area is represented by a strictly rectangular extent, these two points are sufficient to reconstruct the entire transformation. Using four points would make no difference in the final result, as the remaining corners are mathematically derived from the same bounding box.

* the stitched image is already aligned without complex local deformation,
* an affine transformation is sufficient to move from image space to geographic space,
* the provided bounding box is perfectly consistent with the image (exact alignment with no offset).

### 2.3 Spatial Reference System

The script applies an explicit conversion to Web Mercator (EPSG:3857):

1. longitude conversion -> metric X,
2. latitude conversion -> metric Y,
3. construction of metric extent `[min_x, min_y, max_x, max_y]`.

Formulation used (Earth radius R = 6378137):

$$
X = R \cdot \text{rad}(\lambda), \quad
Y = R \cdot \ln\left(\tan\left(\frac{\pi}{4} + \frac{\text{rad}(\varphi)}{2}\right)\right)
$$

The EPSG:3857 choice is consistent with the web origin of raster tiles.

### 2.4 Construction of Affine Transform

The transform is calculated via `rasterio.from_bounds` from:

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

### 2.5 Writing Optimized GeoTIFF

The script writes `data/el_harrach_georef.tif` with the following options:

* GTiff driver,
* 3 RGB bands,
* crs = EPSG:3857,
* DEFLATE compression,
* predictor = 2,
* internal tiling 256x256.

These parameters reduce disk volume and accelerate windowed reads during segmentation/vectorization steps.

Minimal excerpt (GeoTIFF writing):

```py
with rasterio.open(output_tif, "w", driver="GTiff", crs="EPSG:3857", transform=transform) as dst:
	dst.write(img_np[:, :, 0], 1)
	dst.write(img_np[:, :, 1], 2)
	dst.write(img_np[:, :, 2], 3)
```

### 2.6 Validation Performed in Lab

Typical verifications:

* opening the GeoTIFF in QGIS/ArcGIS,
* visual control of alignment with reference basemaps,
* verification of CRS and extent metadata.

The conversion to EPSG:3857 is then imposed as a precondition in several downstream scripts (vectorization, cleaning, visualization).

### 2.7 Outputs and Impact on Experimental Pipeline

Main output:

* `data/el_harrach_georef.tif`

This file becomes the single input to the vectorization chain:

* extraction of polygon classes,
* extraction of linear classes,
* geometric cleaning,
* visualization mask production.

### 2.8 Conclusion

* precision directly depends on the quality of the input bounding box, from reliable ground data,
* two control points (opposite corners) are sufficient because the extent is strictly rectangular and perfectly known,
* the result obtained is equivalent to a four-point configuration in this particular case,
* approximation inherent to Mercator projection (area distortions),
* absence of additional ground control points (GCP) does not affect overall precision in this specific context.

### 2.9 QGIS Verification Figure

Figure 2 - First verification of vectorization and georeferencing in QGIS

<img src="images/scripts/1_qgis_georef_check_poly.png" alt="QGIS georef and vectorization verification" width="100%">
