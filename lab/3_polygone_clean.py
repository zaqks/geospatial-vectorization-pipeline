import geopandas as gpd
from shapely.geometry import MultiPolygon, Polygon
import numpy as np
import sys
import os

os.environ["OGR_GEOJSON_MAX_OBJ_SIZE"] = "0"

# ─────────────────────────────────────────────
# CONFIGURATION  <- adjust these thresholds
# All values are in METERS (script reprojects internally if needed)
# ─────────────────────────────────────────────
MIN_AREA         = 2       # drop polygons smaller than this (m²) — ~1.4m x 1.4m
MIN_WIDTH        = 0.5     # drop slivers whose bounding-box short side < this (m)
#SLIVER_RATIO     = 0.02    # area / perimeter² below this → sliver
POINT_LIKE_SIZE  = 1.0     # bounding-box both sides below this (m) → point-like


def get_bbox_dims(geom):
    """Return (short_side, long_side) of the minimum rotated bounding rectangle."""
    if geom is None or geom.is_empty:
        return 0, 0
    mrr = geom.minimum_rotated_rectangle
    if mrr.is_empty:
        return 0, 0
    coords = list(mrr.exterior.coords)
    side_a = ((coords[1][0]-coords[0][0])**2 + (coords[1][1]-coords[0][1])**2) ** 0.5
    side_b = ((coords[2][0]-coords[1][0])**2 + (coords[2][1]-coords[1][1])**2) ** 0.5
    return min(side_a, side_b), max(side_a, side_b)


def is_point_like(geom, threshold):
    w, h = get_bbox_dims(geom)
    return w < threshold and h < threshold


def is_sliver(geom, min_width, sliver_ratio):
    w, _ = get_bbox_dims(geom)
    if w < min_width:
        return True
    p = geom.length
    if p == 0:
        return True
    compactness = geom.area / (p ** 2)
    return compactness < sliver_ratio


def check_not_empty(gdf, step_name):
    if len(gdf) == 0:
        print(f"\n  WARNING: 0 features remain after '{step_name}'. Check your thresholds.")
        print("  The most common cause is a CRS in degrees — but this script")
        print("  reprojects to meters automatically, so check if reprojection failed.")
        sys.exit(1)


def clean_polygons(input_path, output_path,
                   min_area=MIN_AREA,
                   min_width=MIN_WIDTH,
                   #sliver_ratio=SLIVER_RATIO,
                   point_like_size=POINT_LIKE_SIZE):

    print(f"Loading {input_path} ...")
    gdf = gpd.read_file(input_path)
    original_crs = gdf.crs
    original_count = len(gdf)
    print(f"  {original_count} features loaded.")
    print(f"  CRS: {original_crs}")

    # Drop null or empty geometries
    gdf = gdf[~gdf.geometry.isna()].reset_index(drop=True)
    gdf = gdf[~gdf.geometry.is_empty].reset_index(drop=True)
    print(f"  {len(gdf)} features after dropping null/empty geometries.")

    # Keep only polygon types
    gdf = gdf[gdf.geometry.geom_type.isin(["Polygon", "MultiPolygon"])].reset_index(drop=True)
    print(f"  {len(gdf)} features after keeping only Polygon/MultiPolygon types.")
    check_not_empty(gdf, "type filter")

    # Reproject to meter-based CRS if currently in degrees
    if gdf.crs and gdf.crs.is_geographic:
        print(f"  CRS is geographic (degrees) — reprojecting to EPSG:3857 for metric size checks ...")
        gdf = gdf.to_crs(epsg=3857)
    elif gdf.crs is None:
        print("  WARNING: No CRS defined. Assuming coordinates are already in meters.")

    # Explode multi-polygons
    gdf = gdf.explode(index_parts=False).reset_index(drop=True)
    gdf = gdf[gdf.geometry.geom_type == "Polygon"].reset_index(drop=True)
    print(f"  {len(gdf)} features after exploding multi-polygons.")
    check_not_empty(gdf, "explode")

    # 1. Remove point-like geometries
    mask_point = gdf.geometry.apply(lambda g: is_point_like(g, point_like_size))
    n_point = int(mask_point.sum())
    gdf = gdf[~mask_point].reset_index(drop=True)
    print(f"  Removed {n_point} point-like polygons.")
    check_not_empty(gdf, "point-like filter")

    # 2. Remove small polygons
    areas = gdf.geometry.area
    mask_small = areas < min_area
    n_small = int(mask_small.sum())
    gdf = gdf[~mask_small].reset_index(drop=True)
    print(f"  Removed {n_small} small polygons (area < {min_area} m²).")
    check_not_empty(gdf, "area filter")

    # 3. Remove sliver polygons
    #mask_sliver = gdf.geometry.apply(lambda g: is_sliver(g, min_width, sliver_ratio))
    #n_sliver = int(mask_sliver.sum())
    #gdf = gdf[~mask_sliver].reset_index(drop=True)
    #print(f"  Removed {n_sliver} sliver polygons.")
    #check_not_empty(gdf, "sliver filter")

    # Reproject back to original CRS
    if original_crs and gdf.crs != original_crs:
        print(f"  Reprojecting back to original CRS ({original_crs}) ...")
        gdf = gdf.to_crs(original_crs)

    total_removed = original_count - len(gdf)
    print(f"\n  Total removed: {total_removed}  ->  {len(gdf)} polygons kept.")

    gdf.to_file(output_path, driver="GeoJSON")
    print(f"  Saved to {output_path}")
    return gdf


if __name__ == "__main__":
    input_file  = sys.argv[1] if len(sys.argv) > 1 else "polygons.geojson"
    output_file = sys.argv[2] if len(sys.argv) > 2 else "polygons_clean.geojson"
    clean_polygons(input_file, output_file)
