## 1. Data Acquisition (lab approach / scripts)

### 1.1 Step Objective

The goal of this phase is to download a scanned map covering the target municipality with sufficient detail level to allow color-based vectorization. In the lab folder, this step is mainly implemented by:

- 0_data.py
- 0_legend_extract.py
- 0_legend_overlay_poly.py
- 0_legend_overlay_line.py

This phase comprises two aspects:

1. spatial acquisition (downloading and assembling raster tiles),
2. semantic acquisition (building the legend table and visual verification of classes).

### 1.2 Spatial Delimitation of Study Area

The 0_data.py script uses Nominatim (via geopy) to geocode the municipality "El Harrach, Algeria" and automatically retrieve a bounding box (south, north, west, east).

Assumptions retained in the lab:

- the Nominatim bounding box is sufficiently close to the useful extent,
- padding is added to avoid cutting features at zone edges.

Important technical parameters:

- ZOOM = 18
- TILE_SIZE = 256
- padding = 1

Zoom level z18 provides detailed resolution (trade-off between precision and data volume).

### 1.3 Geographic to Tile Grid Conversion

The script implements:

- latlon_to_tile(lat, lon, zoom)
- tile_to_latlon(x, y, zoom)

These functions ensure conversion between:

- geographic coordinates (WGS84, lat/lon),
- web tile indices (x, y, z) in Web Mercator projection.

This conversion is fundamental to know exactly which tiles to download and to calculate the actual extent of the mosaicked image.

Minimal excerpt (from lab/0_data.py):

```py
def latlon_to_tile(lat, lon, zoom):
	lat_rad = math.radians(lat)
	n = 2.0**zoom
	x = int((lon + 180.0) / 360.0 * n)
	y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
	return x, y
```

### 1.4 Downloading, Local Cache and Assembly

Tiles are retrieved from Carto basemaps (voyager_nolabels style) and stored in a local cache:

- data/tiles/18/x_y.png

The cache allows:

- reproducibility of tests,
- reduction of network requests,
- acceleration of experimental pipeline reruns.

Minimal excerpt (cache + downloading):

```py
tile_path = f"{cache_dir}/{x}_{y}.png"
if os.path.exists(tile_path):
	tiles[(x, y)] = Image.open(tile_path).convert("RGB")
else:
	r = requests.get(url, headers=headers, timeout=10)
```

After downloading, tiles are "stitched" into a single image:

- output: data/el_harrach_highres_map.png

The script also calculates the final extent of the mosaic (north/south/west/east), which facilitates geometric verification prior to georeferencing.

### 1.5 Color Signature Extraction

The 0_legend_extract.py script performs color analysis of the complete image:

- reading the RGB image,
- flattening pixels,
- aggregating occurrences by triplet (r, g, b) with Polars,
- calculating appearance percentages,
- exporting dominant classes to data/legend.csv.

Threshold applied in the export:

- only colors >= 0.1% are retained.

Significance of this step:

- identify dominant hues before segmentation,
- detect rare or noisy classes,
- prepare a class reference usable in vectorization scripts.

### 1.6 Visual Verification of Legend

The overlay scripts (0_legend_overlay_poly.py, 0_legend_overlay_line.py) apply color masking by class from legend_class_geo.csv.

Principle:

1. hex to BGR conversion,
2. detection of target pixels with tolerance (often 1),
3. generation of a control image where detected pixels are painted red,
4. export class by class in output/overlays.

For lines, morphological preprocessing (closing and dilation) is added to make fine linear patterns visually legible.

### 1.7 Outputs and Artifacts of Acquisition Phase

Main products:

- base raster: data/el_harrach_highres_map.png
- table of dominant colors: data/legend.csv
- business class table: data/legend_class_geo.csv (add geometry & z-index columns)
- control overlays: output/overlays/poly/*.png and output/overlays/line/*.png

These artifacts directly feed into the following steps (georeferencing and vectorization).

### 1.8 Conclusion

- dependence on source color quality (compression, aliasing, local variations),
- strong sensitivity of masking to chosen tolerance,
- risk of confusion between chromatically close classes,
- extraction of semantic classes still semi-supervised (legend table maintained manually).

Despite these limitations, the acquisition phase provides a robust experimental basis for the subsequent geospatial chain.

### 1.9 Figures (script captures)

Figure 1 - High resolution map download (input)

<img src="images/scripts/0_input.png" alt="High resolution map download" width="100%">
