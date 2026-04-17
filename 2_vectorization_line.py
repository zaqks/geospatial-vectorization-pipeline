import os
import numpy as np
import pandas as pd
import rasterio
import geopandas as gpd
from tqdm import tqdm
from PIL import Image, ImageDraw
from shapely.geometry import LineString
from skimage.morphology import medial_axis

# %%
# -------------------------
# CONFIG
# -------------------------
raster_path = "data/el_harrach_georef.tif"
output_dir = "output/vect/line"
os.makedirs(output_dir, exist_ok=True)

COLOR_TOLERANCE = 1
EXPORT_TO_WGS84 = True

# %%
# -------------------------
# LEGEND & COLORS
# -------------------------
df = pd.read_csv("data/legend_class_geo.csv")
df = df[df.geometry == "line"]

def hex_to_rgb(hex_color: str):
    hex_color = hex_color.lstrip("#")
    return (int(hex_color[0:2], 16),
            int(hex_color[2:4], 16),
            int(hex_color[4:6], 16))

color_class_map = {
    hex_to_rgb(row["hex"]): row["class"]
    for _, row in df.iterrows()
}

print(f"Loaded {len(color_class_map)} line classes")

# %%
# -------------------------
# READ RASTER
# -------------------------
with rasterio.open(raster_path) as src:
    img_data = src.read()
    transform = src.transform
    crs = src.crs
    inv_transform = ~transform # Used for PNG drawing

img_np = np.transpose(img_data, (1, 2, 0))[:, :, :3].astype(np.uint8)

print("\nRaster info:")
print("Shape:", img_np.shape)
print("CRS:", crs)

# %%
# -------------------------
# SKELETON TO LINES HELPER
# -------------------------
def skeleton_to_lines(skel):
    """Walks the skeleton pixels to create LineString geometries"""
    lines = []
    visited = skel.copy()
    h, w = skel.shape

    for y in range(h):
        for x in range(w):
            if not skel[y, x] or not visited[y, x]:
                continue

            coords = []
            cy, cx = y, x

            while True:
                coords.append((cx, cy))
                visited[cy, cx] = False
                
                found = False
                # Check 8-neighbors
                for dy in [-1, 0, 1]:
                    for dx in [-1, 0, 1]:
                        ny, nx = cy + dy, cx + dx
                        if 0 <= ny < h and 0 <= nx < w and visited[ny, nx]:
                            cy, cx = ny, nx
                            found = True
                            break
                    if found: break
                if not found: break

            if len(coords) > 2:
                lines.append(LineString(coords))
    return lines

# %%
# -------------------------
# PROCESS EACH CLASS
# -------------------------
for rgb, class_name in tqdm(color_class_map.items(), desc="Processing classes"):

    print(f"\n------------------------------")
    print(f"Class: {class_name} | RGB: {rgb}")

    # 1. Create Mask
    target = np.array(rgb, dtype=np.int16)
    mask = np.all(np.abs(img_np.astype(np.int16) - target) <= COLOR_TOLERANCE, axis=2)

    if not np.any(mask):
        print("⚠️ Empty mask → skipping")
        continue

    # 2. Extract Skeleton (Medial Axis)
    # This turns thick pixel lines into 1-pixel thin centerlines
    skel, _ = medial_axis(mask.astype(bool), return_distance=True)
    
    # 3. Vectorize (Pixel Space)
    pixel_lines = skeleton_to_lines(skel)
    
    if not pixel_lines:
        print("⚠️ No lines found in skeleton → skipping")
        continue

    # 4. Transform to Geo Coordinates
    geo_lines = []
    for line in pixel_lines:
        # rasterio.transform.xy handles the math to move pixel (x,y) to Map (E,N)
        geo_coords = [transform * pt for pt in line.coords]
        if len(geo_coords) >= 2:
            geo_lines.append(LineString(geo_coords))

    # 5. Save GeoJSON
    gdf = gpd.GeoDataFrame(geometry=geo_lines, crs=crs)
    gdf["class"] = class_name

    if EXPORT_TO_WGS84:
        gdf = gdf.to_crs("EPSG:4326")

    geojson_path = os.path.join(output_dir, f"{class_name}.geojson")
    gdf.to_file(geojson_path, driver="GeoJSON")
    print(f"Saved GeoJSON: {geojson_path}")

    # -------------------------
    # 6. PNG OVERLAY (FIXED)
    # -------------------------
    overlay = Image.fromarray(img_np).convert("RGBA")
    draw = ImageDraw.Draw(overlay)
    line_color = (255, 0, 0, 255) # Solid red

    for line in pixel_lines:
        # pixel_lines are already in (x, y) pixel space, so we draw directly
        # If we used geo_lines, we'd have to use inv_transform * pt
        draw.line(list(line.coords), fill=line_color, width=2)

    png_path = os.path.join(output_dir, f"{class_name}.png")
    overlay.save(png_path)
    print(f"Saved PNG: {png_path}")

print("\n✅ DONE")