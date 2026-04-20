import os
import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import rasterize
from PIL import Image
from tqdm import tqdm
import sys

# ─────────────────────────────────────────────
# CONFIGURATION (meters)
# ─────────────────────────────────────────────
MIN_AREA_M2        = 1       # absolute area threshold
MIN_WIDTH_M        = 0.5     # minimum bbox short side
POINT_LIKE_SIZE_M  = 1.0     # both bbox sides under this → point-like
SLIVER_RATIO       = 0.02    # area / perimeter² threshold


# ─────────────────────────────────────────────
# GEOMETRY HELPERS
# ─────────────────────────────────────────────
def get_bbox_dims(geom):
    """Return (short_side, long_side) of minimum rotated bounding rectangle."""
    if geom is None or geom.is_empty:
        return 0, 0

    mrr = geom.minimum_rotated_rectangle
    coords = list(mrr.exterior.coords)

    side_a = np.hypot(coords[1][0] - coords[0][0],
                      coords[1][1] - coords[0][1])
    side_b = np.hypot(coords[2][0] - coords[1][0],
                      coords[2][1] - coords[1][1])

    return min(side_a, side_b), max(side_a, side_b)


def is_point_like(geom, threshold):
    w, h = get_bbox_dims(geom)
    return (w < threshold) and (h < threshold)


def is_sliver(geom, min_width, sliver_ratio):
    w, _ = get_bbox_dims(geom)

    if w < min_width:
        return True

    p = geom.length
    if p == 0:
        return True

    compactness = geom.area / (p ** 2)
    return compactness < sliver_ratio


# ─────────────────────────────────────────────
# CLEAN FUNCTION
# ─────────────────────────────────────────────
def clean_and_debug_vector(geojson_path, output_dir, min_area_m2, reference_raster_path):

    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(geojson_path))[0]

    gdf = gpd.read_file(geojson_path)
    if gdf.empty:
        print(f"No data found in {geojson_path}")
        return

    original_crs = gdf.crs

    # -------------------------
    # Convert to metric CRS
    # -------------------------
    gdf = gdf.to_crs(epsg=3857)

    initial_count = len(gdf)

    # -------------------------
    # 1. Remove point-like
    # -------------------------
    mask_point = gdf.geometry.apply(lambda g: is_point_like(g, POINT_LIKE_SIZE_M))
    gdf = gdf[~mask_point]

    # -------------------------
    # 2. Remove small area
    # -------------------------
    gdf = gdf[gdf.geometry.area >= min_area_m2]

    # -------------------------
    # 3. Remove slivers
    # -------------------------
    mask_sliver = gdf.geometry.apply(
        lambda g: is_sliver(g, MIN_WIDTH_M, SLIVER_RATIO)
    )
    gdf = gdf[~mask_sliver]

    final_count = len(gdf)

    print(f"[{base_name}] Removed {initial_count - final_count} polygons "
          f"(point-like + small + slivers).")

    if gdf.empty:
        print(f"[{base_name}] WARNING: No geometries left after cleaning.")
        return

    # -------------------------
    # Back to original CRS
    # -------------------------
    gdf = gdf.to_crs(original_crs)

    # -------------------------
    # Save cleaned GeoJSON
    # -------------------------
    clean_geojson_path = os.path.join(output_dir, f"{base_name}_cleaned.geojson")
    gdf.to_file(clean_geojson_path, driver="GeoJSON")

    # -------------------------
    # DEBUG RASTER OUTPUT
    # -------------------------
    with rasterio.open(reference_raster_path) as src:
        h, w = src.height, src.width
        transform = src.transform
        raster_crs = src.crs

    gdf_raster = gdf.to_crs(raster_crs)

    if not gdf_raster.empty:
        mask = rasterize(
            [(geom, 1) for geom in gdf_raster.geometry],
            out_shape=(h, w),
            transform=transform,
            fill=0,
            dtype=np.uint8
        )

        img = np.zeros((h, w, 3), dtype=np.uint8)
        img[mask == 1] = [255, 0, 0]

        Image.fromarray(img).save(
            os.path.join(output_dir, f"{base_name}.png")
        )

    print(f"Saved: {clean_geojson_path}")


# ─────────────────────────────────────────────
# BATCH EXECUTION
# ─────────────────────────────────────────────
from pathlib import Path

if __name__ == "__main__":

    input_folder = Path("output/vect/poly")
    output_folder = Path("output/clean/poly")
    ref_raster = "data/el_harrach_georef.tif"

    output_folder.mkdir(parents=True, exist_ok=True)

    geojson_files = list(input_folder.glob("*.geojson"))

    if not geojson_files:
        print("No GeoJSON files found.")

    for geojson_path in tqdm(geojson_files, desc="Processing GeoJSON files"):
        try:
            clean_and_debug_vector(
                geojson_path=str(geojson_path),
                output_dir=str(output_folder),
                min_area_m2=MIN_AREA_M2,
                reference_raster_path=ref_raster
            )
        except Exception as e:
            print(f"Failed on {geojson_path.name}: {e}")