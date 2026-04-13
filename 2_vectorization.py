import rasterio
import numpy as np
from rasterio.features import shapes
import geopandas as gpd
from shapely.geometry import shape
import imageio
import os
from tqdm import tqdm

# 📂 Input raster
raster_path = "data/el_harrach_georef.tif"
output_dir = "output"
os.makedirs(output_dir, exist_ok=True)

# 🎨 COLOR → CLASS MAP
color_class_map = {
    "#d9d0c9": "building",
    "#f3e3dd": "military_area"
}

# 🔧 tolerance for color matching
tolerance = 10


# Convert HEX → RGB
def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return np.array([int(hex_color[i : i + 2], 16) for i in (0, 2, 4)])


# Read raster
with rasterio.open(raster_path) as src:
    img = src.read()
    transform = src.transform
    crs = src.crs

# Convert to (H, W, C)
img = np.transpose(img, (1, 2, 0))[:, :, :3].astype(np.uint8)

# -------------------------
# PROCESS EACH CLASS (WITH PROGRESS BAR)
# -------------------------
for hex_color, class_name in tqdm(color_class_map.items(), desc="Processing classes"):

    target = hex_to_rgb(hex_color)

    # 🎯 MASK
    mask = np.all(np.abs(img - target) <= tolerance, axis=2)

    if not mask.any():
        print(f"⚠️ No pixels found for class: {class_name}")
        continue

    # -------------------------
    # VECTORIZE MASK
    # -------------------------
    geoms = []
    for geom, val in shapes(mask.astype(np.uint8), transform=transform):
        if val == 1:
            geoms.append(shape(geom))

    gdf = gpd.GeoDataFrame(geometry=geoms, crs=crs)
    gdf["class"] = class_name

    geojson_path = os.path.join(output_dir, f"{class_name}.geojson")
    gdf.to_file(geojson_path, driver="GeoJSON")

    # -------------------------
    # DEBUG OVERLAY
    # -------------------------
    overlay = img.copy()

    alpha = 0.5

    highlight = np.zeros_like(img)
    highlight[:, :, 0] = 255  # red

    overlay[mask] = ((1 - alpha) * overlay[mask] + alpha * highlight[mask]).astype(
        np.uint8
    )

    overlay_path = os.path.join(output_dir, f"{class_name}_overlay.png")
    imageio.imwrite(overlay_path, overlay)

print("\n✅ Done processing all classes")
