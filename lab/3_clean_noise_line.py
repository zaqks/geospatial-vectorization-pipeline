#!/usr/bin/env python3

import os
import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import rasterize
from PIL import Image

# -------------------------
# CONFIG
# -------------------------
# Input from the vectorization script
input_geojson = "output/vect/line/autoroute.geojson"
# Reference raster to maintain consistent sizes/bounds
reference_raster = "data/el_harrach_georef.tif" 

output_dir = "output/clean/line"
os.makedirs(output_dir, exist_ok=True)

MIN_LENGTH_METERS = 50
SIMPLIFY_TOLERANCE = 0.00005

def clean_road_network(input_path, ref_raster_path):
    print(f"--- Loading: {input_path} ---")
    
    if not os.path.exists(input_path):
        print(f"File not found: {input_path}")
        return

    gdf = gpd.read_file(input_path)

    if gdf.empty:
        print("Empty GeoJSON. Skipping.")
        return

    # Load Reference Metadata to match sizes exactly
    with rasterio.open(ref_raster_path) as src:
        ref_transform = src.transform
        ref_crs = src.crs
        ref_height = src.height
        ref_width = src.width

    original_count = len(gdf)

    # 1. Remove invalid
    gdf = gdf[gdf.geometry.notnull()]
    gdf = gdf[gdf.geometry.is_valid]

    # 2. Length filter (meters)
    # We use a temporary CRS (3857) to calculate length in meters
    gdf_m = gdf.to_crs(epsg=3857)
    gdf = gdf[gdf_m.geometry.length > MIN_LENGTH_METERS]

    # 3. Simplify
    gdf.geometry = gdf.geometry.simplify(
        tolerance=SIMPLIFY_TOLERANCE,
        preserve_topology=True
    )

    print(f"Removed {original_count - len(gdf)} segments")

    if gdf.empty:
        print("Nothing left after cleaning.")
        return

    # Prepare Paths
    base = os.path.basename(input_path).replace(".geojson", "")
    out_geojson = os.path.join(output_dir, f"{base}_cleaned.geojson")
    out_png = os.path.join(output_dir, f"{base}_preview.png")

    # Save Cleaned Vector
    gdf.to_file(out_geojson, driver="GeoJSON")
    print(f"Saved GeoJSON: {out_geojson}")

    # -------------------------
    # FIXED SIZE PNG EXPORT
    # -------------------------
    # Ensure the GeoDataFrame matches the reference CRS (usually UTM or the original projection)
    gdf_ref_crs = gdf.to_crs(ref_crs)

    # Rasterize using the reference transform and dimensions
    # This ensures the lines stay in the same place relative to the map
    mask = rasterize(
        [(geom, 1) for geom in gdf_ref_crs.geometry if geom is not None],
        out_shape=(ref_height, ref_width),
        transform=ref_transform,
        fill=0,
        dtype=np.uint8
    )

    # Create the RGB image: Black background, Red lines
    img = np.zeros((ref_height, ref_width, 3), dtype=np.uint8)
    img[mask == 1] = (255, 0, 0)

    Image.fromarray(img).save(out_png)
    print(f"Saved Fixed-Size PNG: {out_png} ({ref_width}x{ref_height})")


if __name__ == "__main__":
    # Check if reference raster exists before starting
    if os.path.exists(reference_raster):
        clean_road_network(input_geojson, reference_raster)
    else:
        print(f"Reference raster missing: {reference_raster}. Cannot determine output size.")