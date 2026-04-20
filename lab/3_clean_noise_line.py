#!/usr/bin/env python3
import os
import numpy as np
import geopandas as gpd
import rasterio
from rasterio import features
from shapely.geometry import shape, LineString, MultiLineString
from skimage.morphology import skeletonize
from scipy.ndimage import gaussian_filter1d
from PIL import Image

# -------------------------
# CONFIG
# -------------------------
INPUT_GEOJSON = "output/vect/line/autoroute.geojson"
REFERENCE_RASTER = "data/el_harrach_georef.tif"
OUTPUT_DIR = "output/clean/line"

# How wide the 'scribble' zone is. Increase if lines don't merge.
BUFFER_METERS = 2 # 15
# Precision of the skeletonization. 1.0 = 1 meter per pixel.
RASTER_RES = 1 # 1.0 
# Final curve smoothing.
SMOOTHING_SIGMA = 1.0 # 2

os.makedirs(OUTPUT_DIR, exist_ok=True)

def log(msg):
    print(f"[INFO] {msg}")

def smooth_geometry(geometry, sigma=2.0):
    """Applies Gaussian smoothing to coordinate arrays."""
    if geometry is None or geometry.is_empty:
        return geometry
    if geometry.geom_type == 'LineString':
        coords = np.array(geometry.coords)
        if len(coords) < 3: return geometry
        x = gaussian_filter1d(coords[:, 0], sigma=sigma)
        y = gaussian_filter1d(coords[:, 1], sigma=sigma)
        return LineString(np.column_stack((x, y)))
    return geometry

def clean_to_centerline_with_preview(input_path, ref_raster_path):
    log(f"Processing: {input_path}")
    
    # 1. Load and project to Meters
    gdf = gpd.read_file(input_path)
    if gdf.empty: return
    original_crs = gdf.crs
    gdf_m = gdf.to_crs(epsg=3857)

    # 2. Merge all scribbles into one solid "tube"
    log("Merging scribbles into thick path...")
    thick_path = gdf_m.geometry.buffer(BUFFER_METERS, cap_style=2, join_style=2).unary_union
    
    # 3. Create a local raster for skeletonization
    minx, miny, maxx, maxy = thick_path.bounds
    width = int((maxx - minx) / RASTER_RES)
    height = int((maxy - miny) / RASTER_RES)
    
    # Check for valid dimensions
    if width <= 0 or height <= 0:
        log("Geometry too small to process.")
        return

    transform = rasterio.transform.from_origin(minx, maxy, RASTER_RES, RASTER_RES)
    
    mask = features.rasterize(
        [thick_path],
        out_shape=(height, width),
        transform=transform,
        fill=0,
        default_value=1,
        dtype=np.uint8
    )

    # 4. Skeletonize (find the mathematical center)
    skeleton = skeletonize(mask)

    # 5. Extract vector line from skeleton
    # We use approximate_polygon to turn pixels back into a clean path
    shapes_gen = features.shapes(skeleton.astype(np.uint8), mask=skeleton, transform=transform)
    
    lines = []
    for geom, val in shapes_gen:
        # Each skeleton part is turned into a simplified line
        s = shape(geom).simplify(RASTER_RES)
        if s.geom_type == 'Polygon':
            lines.append(s.exterior)
        else:
            lines.append(s)

    # Create GeoDataFrame for the new centerline
    clean_gdf = gpd.GeoDataFrame(geometry=lines, crs="EPSG:3857")
    
    # 6. Smooth the result for the "clean pen" look
    clean_gdf.geometry = clean_gdf.geometry.apply(lambda g: smooth_geometry(g, sigma=SMOOTHING_SIGMA))
    
    # Back to original CRS
    final_gdf = clean_gdf.to_crs(original_crs)

    # 7. Save Cleaned GeoJSON
    base = os.path.basename(input_path).replace(".geojson", "")
    out_geojson = os.path.join(OUTPUT_DIR, f"{base}_centerline.geojson")
    final_gdf.to_file(out_geojson, driver="GeoJSON")
    log(f"Saved: {out_geojson}")

    # -------------------------
    # 8. PNG PREVIEW (Using your Reference Raster)
    # -------------------------
    if os.path.exists(ref_raster_path):
        with rasterio.open(ref_raster_path) as src:
            ref_transform = src.transform
            ref_crs = src.crs
            ref_height = src.height
            ref_width = src.width

        # Project cleaned lines to the raster's CRS
        gdf_ref_crs = final_gdf.to_crs(ref_crs)
        
        # Rasterize the clean lines
        preview_mask = features.rasterize(
            [(geom, 1) for geom in gdf_ref_crs.geometry if geom is not None],
            out_shape=(ref_height, ref_width),
            transform=ref_transform,
            fill=0,
            dtype=np.uint8
        )
        
        # Create RGB image (Red line on black background)
        img = np.zeros((ref_height, ref_width, 3), dtype=np.uint8)
        img[preview_mask == 1] = (255, 0, 0)
        
        out_png = os.path.join(OUTPUT_DIR, f"{base}_preview.png")
        Image.fromarray(img).save(out_png)
        log(f"Saved PNG Preview: {out_png}")

if __name__ == "__main__":
    clean_to_centerline_with_preview(INPUT_GEOJSON, REFERENCE_RASTER)