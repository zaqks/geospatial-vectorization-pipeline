import os
import numpy as np
import pandas as pd
import rasterio
import geopandas as gpd
from tqdm import tqdm
from shapely.geometry import shape, LineString
from rasterio.features import shapes, rasterize
from skimage.morphology import closing, disk, skeletonize, remove_small_objects, dilation
from PIL import Image

# -------------------------
# CONFIG
# -------------------------
raster_path = "data/el_harrach_georef.tif"
output_dir = "output/vect/railway"
os.makedirs(output_dir, exist_ok=True)

TARGET_CLASS = "railway"
COLOR_TOLERANCE = 5 

# GAP BRIDGING: Increase this radius if the dots are far apart
# This connects dots within ~10-15 pixels of each other
BRIDGE_RADIUS = 7 

MIN_OBJECT_SIZE_M2 = 300 
SIMPLIFY_TOLERANCE = 0.5 
EXPORT_TO_WGS84 = True

# -------------------------
# DATA LOADING
# -------------------------
df = pd.read_csv("data/legend_class_geo.csv")
# Filter specifically for railway
rail_row = df[df["class"] == TARGET_CLASS].iloc[0]

def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return (int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16))

target_rgb = np.array(hex_to_rgb(rail_row["hex"]), dtype=np.int16)

with rasterio.open(raster_path) as src:
    img = src.read()
    transform = src.transform
    crs = src.crs
    h, w = src.height, src.width
    pixel_area = abs(transform[0] * transform[4]) 
    min_object_pixels = int(MIN_OBJECT_SIZE_M2 / pixel_area)

img_np = np.transpose(img, (1, 2, 0))[:, :, :3].astype(np.int16)

# -------------------------
# PROCESSING
# -------------------------

# 1. Create Initial Mask
mask = np.all(np.abs(img_np - target_rgb) <= COLOR_TOLERANCE, axis=2)

if np.any(mask):
    # 2. BRIDGE THE GAPS
    # We use a large closing to turn dots into a continuous "sausage" shape
    continuous_mask = closing(mask, disk(BRIDGE_RADIUS))
    
    # 3. Clean noise
    if min_object_pixels > 0:
        continuous_mask = remove_small_objects(continuous_mask, min_size=min_object_pixels)

    # 4. SKELETONIZE
    # This turns the "sausage" back into a 1-pixel wide centerline
    skeleton = skeletonize(continuous_mask).astype(np.uint8)

    # 5. VECTORIZE
    # Extracting shapes from 1-pixel lines
    results = (
        {'properties': {'val': v}, 'geometry': s}
        for i, (s, v) in enumerate(shapes(skeleton, mask=skeleton > 0, transform=transform))
    )
    
    line_geoms = []
    for g in results:
        poly_shape = shape(g['geometry'])
        # The skeleton shapes often come out as thin Polygons; we take the exterior
        if poly_shape.geom_type == 'Polygon':
            line_geoms.append(poly_shape.exterior)
        elif poly_shape.geom_type == 'MultiPolygon':
            for part in poly_shape.geoms:
                line_geoms.append(part.exterior)

    if line_geoms:
        gdf = gpd.GeoDataFrame(geometry=line_geoms, crs=crs)
        
        # Simplify to smooth out the "pixel steps"
        gdf['geometry'] = gdf.simplify(tolerance=SIMPLIFY_TOLERANCE, preserve_topology=True)
        gdf["class"] = TARGET_CLASS

        if EXPORT_TO_WGS84:
            gdf = gdf.to_crs("EPSG:4326")

        # Save GeoJSON
        out_geojson = os.path.join(output_dir, f"{TARGET_CLASS}.geojson")
        gdf.to_file(out_geojson, driver="GeoJSON")

        # 6. DEBUG PNG PLOT
        # Rasterize the final lines back to an image to check connectivity
        gdf_for_raster = gdf.to_crs(crs)
        debug_mask = rasterize(
            [(geom, 1) for geom in gdf_for_raster.geometry],
            out_shape=(h, w), transform=transform, fill=0, dtype=np.uint8
        )
        
        # Create a black image and paint the lines Red
        out_img = np.zeros((h, w, 3), dtype=np.uint8)
        out_img[debug_mask == 1] = (255, 0, 0) 
        Image.fromarray(out_img).save(os.path.join(output_dir, f"{TARGET_CLASS}_debug.png"))

        print(f"SUCCESS: Railway lines generated. Check {out_geojson}")
else:
    print("Error: No pixels found for the railway color.")