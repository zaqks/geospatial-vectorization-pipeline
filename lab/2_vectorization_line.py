import os
import numpy as np
import pandas as pd
import rasterio
import geopandas as gpd
from tqdm import tqdm
from shapely.geometry import shape
from rasterio.features import shapes, rasterize
from skimage.morphology import closing, disk, skeletonize, remove_small_objects
from PIL import Image

# -------------------------
# CONFIG
# -------------------------
raster_path = "data/el_harrach_georef.tif"
output_dir = "output/vect/line"
os.makedirs(output_dir, exist_ok=True)

COLOR_TOLERANCE = 1
CLOSING_RADIUS = 5 # 1.5
MIN_OBJECT_SIZE_M2 = 500  # Minimum size in square meters
MIN_LINE_LENGTH = 2   
SIMPLIFY_TOLERANCE = 0.3 # 0.3
TARGET_CRS = "EPSG:3857"

# -------------------------
# LEGEND & UTILS
# -------------------------
df = pd.read_csv("data/legend_class_geo.csv")
df = df[(df["geometry"] == "line") & (df["class"] != "railway")]

def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return (int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16))

color_class_map = {hex_to_rgb(row["hex"]): row["class"] for _, row in df.iterrows()}

# -------------------------
# READ RASTER
# -------------------------
with rasterio.open(raster_path) as src:
    img = src.read()
    transform = src.transform
    crs = src.crs
    h, w = src.height, src.width
    # Calculate pixel area (assuming meters if CRS is projected)
    pixel_area = abs(transform[0] * transform[4]) 
    min_object_pixels = int(MIN_OBJECT_SIZE_M2 / pixel_area)

if str(crs) != TARGET_CRS:
    raise ValueError(f"Expected raster CRS {TARGET_CRS}, got {crs}")

img_np = np.transpose(img, (1, 2, 0))[:, :, :3].astype(np.int16)

# -------------------------
# PROCESS EACH CLASS
# -------------------------
for rgb, class_name in tqdm(color_class_map.items(), desc="Processing classes"):
    target = np.array(rgb, dtype=np.int16)
    
    mask = np.all(np.abs(img_np - target) <= COLOR_TOLERANCE, axis=2)
    if not np.any(mask):
        continue

    cleaned_mask = closing(mask, disk(CLOSING_RADIUS))
    
    # Updated to use meter-derived pixel count
    if min_object_pixels > 0:
        cleaned_mask = remove_small_objects(cleaned_mask, min_size=min_object_pixels)

    skeleton = skeletonize(cleaned_mask).astype(np.uint8)

    results = (
        {'properties': {'raster_val': v}, 'geometry': s}
        for i, (s, v) in enumerate(shapes(skeleton, mask=skeleton > 0, transform=transform))
    )
    
    line_geoms = []
    for g in results:
        poly_shape = shape(g['geometry'])
        if poly_shape.geom_type == 'Polygon':
            line_geoms.append(poly_shape.exterior)
        elif poly_shape.geom_type == 'MultiPolygon':
            for part in poly_shape.geoms:
                line_geoms.append(part.exterior)

    if not line_geoms:
        continue

    gdf = gpd.GeoDataFrame(geometry=line_geoms, crs=crs)
    gdf['geometry'] = gdf.simplify(tolerance=SIMPLIFY_TOLERANCE, preserve_topology=True)
    gdf = gdf[gdf.length > MIN_LINE_LENGTH]
    gdf["class"] = class_name

    class_name_safe = class_name.replace(" ", "_")
    out_geojson = os.path.join(output_dir, f"{class_name_safe}.geojson")
    gdf.to_file(out_geojson, driver="GeoJSON")

    if not gdf.empty:
        debug_mask = rasterize(
            [(geom, 1) for geom in gdf.geometry],
            out_shape=(h, w), transform=transform, fill=0, dtype=np.uint8
        )
        out_img = np.zeros((h, w, 3), dtype=np.uint8)
        out_img[debug_mask == 1] = (255, 0, 0) 
        Image.fromarray(out_img).save(os.path.join(output_dir, f"{class_name_safe}.png"))

print(f"\nSUCCESS — Centerlines refined (Min Area: {MIN_OBJECT_SIZE_M2}m2) and saved to {output_dir}")
