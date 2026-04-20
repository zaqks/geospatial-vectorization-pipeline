import os
import cv2
import numpy as np
import pandas as pd
import rasterio
import geopandas as gpd
from shapely.geometry import shape
from rasterio.features import shapes, rasterize
from skimage.morphology import skeletonize, remove_small_objects
from PIL import Image

# -------------------------
# CONFIG
# -------------------------
raster_path = "data/el_harrach_georef.tif"
output_dir = "output/vect/railway"
os.makedirs(output_dir, exist_ok=True)

TARGET_CLASS = "railway"
COLOR_TOLERANCE = 1
BRIDGE_RADIUS = 20 #15
MIN_OBJECT_SIZE_M2 = 750 #500
SIMPLIFY_TOLERANCE = 0.3 #0.1
EXPORT_TO_WGS84 = True

# -------------------------
# DATA LOADING
# -------------------------
df = pd.read_csv("data/legend_class_geo.csv")
rail_row = df[df["class"] == TARGET_CLASS].iloc[0]

def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return [int(hex_color[i:i+2], 16) for i in (0, 2, 4)]

rgb_val = hex_to_rgb(rail_row["hex"])
lower_b = np.array([max(0, c - COLOR_TOLERANCE) for c in rgb_val], dtype=np.uint8)
upper_b = np.array([min(255, c + COLOR_TOLERANCE) for c in rgb_val], dtype=np.uint8)

with rasterio.open(raster_path) as src:
    # Read only RGB bands and use a more memory-efficient layout
    img = src.read((1, 2, 3))
    transform = src.transform
    crs = src.crs
    h, w = src.height, src.width
    pixel_area = abs(transform[0] * transform[4]) 
    min_object_pixels = int(MIN_OBJECT_SIZE_M2 / pixel_area)

# Convert to HWC for OpenCV (use moveaxis to avoid unnecessary copies where possible)
img_np = np.moveaxis(img, 0, -1)

# -------------------------
# OPTIMIZED PROCESSING
# -------------------------

# 1. Fast Masking using OpenCV
mask = cv2.inRange(img_np, lower_b, upper_b)

if np.any(mask):
    # 2. Fast Gap Bridging using OpenCV Morphology
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (BRIDGE_RADIUS * 2 + 1, BRIDGE_RADIUS * 2 + 1))
    continuous_mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    
    # 3. Clean Noise
    if min_object_pixels > 0:
        continuous_mask = remove_small_objects(continuous_mask.astype(bool), min_size=min_object_pixels)

    # 4. Skeletonize (Scikit-image is efficient here)
    skeleton = skeletonize(continuous_mask).astype(np.uint8)

    # 5. Fast Vectorization
    # Using a list comprehension directly into GeoDataFrame
    results = shapes(skeleton, mask=skeleton > 0, transform=transform)
    
    line_geoms = []
    for s, v in results:
        poly_shape = shape(s)
        if poly_shape.geom_type == 'Polygon':
            line_geoms.append(poly_shape.exterior)
        elif poly_shape.geom_type == 'MultiPolygon':
            for part in poly_shape.geoms:
                line_geoms.append(part.exterior)

    if line_geoms:
        gdf = gpd.GeoDataFrame({'geometry': line_geoms}, crs=crs)
        gdf['geometry'] = gdf.simplify(tolerance=SIMPLIFY_TOLERANCE, preserve_topology=True)
        gdf["class"] = TARGET_CLASS

        if EXPORT_TO_WGS84:
            gdf = gdf.to_crs("EPSG:4326")

        out_geojson = os.path.join(output_dir, f"{TARGET_CLASS}.geojson")
        gdf.to_file(out_geojson, driver="GeoJSON")

        # 6. PNG DEBUG PLOT
        gdf_for_raster = gdf.to_crs(crs)
        debug_mask = rasterize(
            [(geom, 1) for geom in gdf_for_raster.geometry],
            out_shape=(h, w), transform=transform, fill=0, dtype=np.uint8
        )
        
        out_img = np.zeros((h, w, 3), dtype=np.uint8)
        out_img[debug_mask == 1] = (255, 0, 0) 
        Image.fromarray(out_img).save(os.path.join(output_dir, f"{TARGET_CLASS}_debug.png"))

        print(f"SUCCESS: {TARGET_CLASS} lines generated.")
else:
    print("Error: No pixels found for the railway color.")