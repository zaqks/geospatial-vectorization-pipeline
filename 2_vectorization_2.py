import rasterio
import numpy as np
from rasterio.features import shapes
import geopandas as gpd
from shapely.geometry import shape
import imageio
import os
from tqdm import tqdm
from PIL import Image

# 📂 Input raster
raster_path = "data/el_harrach_georef.tif"
output_dir = "output"
os.makedirs(output_dir, exist_ok=True)

# 📂 Legend image (single file)
legend_path = "data/legend_area_clean/Non-specific_building.png"

# 🔧 tolerance for color matching
tolerance = 10


# -------------------------
# 🎨 HEX ↔ RGB
# -------------------------
def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return np.array([int(hex_color[i:i+2], 16) for i in (0, 2, 4)])


# -------------------------
# 🎯 DOMINANT COLOR EXTRACTOR
# -------------------------
def get_dominant_hex(image_path):
    img = Image.open(image_path).convert("RGB")

    img = img.resize((100, 100))
    pixels = np.array(img).reshape(-1, 3)

    # Remove near-white background
    pixels = pixels[np.linalg.norm(pixels - [255, 255, 255], axis=1) > 30]

    if len(pixels) == 0:
        raise ValueError(f"No valid pixels found in {image_path}")

    dominant = np.median(pixels, axis=0).astype(int)

    return "#{:02x}{:02x}{:02x}".format(*dominant)


# -------------------------
# 🧠 BUILD COLOR MAP
# -------------------------
class_name = os.path.splitext(os.path.basename(legend_path))[0]
dominant_hex = get_dominant_hex(legend_path)

print(f"{class_name}: {dominant_hex}")

color_class_map = {
    dominant_hex: class_name
}


# -------------------------
# 📥 READ RASTER
# -------------------------
with rasterio.open(raster_path) as src:
    img = src.read()
    transform = src.transform
    crs = src.crs

img = np.transpose(img, (1, 2, 0))[:, :, :3].astype(np.uint8)


# -------------------------
# 🚀 PROCESS EACH CLASS
# -------------------------
for hex_color, class_name in tqdm(color_class_map.items(), desc="Processing classes"):

    target = hex_to_rgb(hex_color)

    mask = np.all(np.abs(img - target) <= tolerance, axis=2)

    if not mask.any():
        print(f"⚠️ No pixels found for class: {class_name}")
        continue

    # -------------------------
    # 🧩 VECTORIZE MASK (WITH PROGRESS)
    # -------------------------
    geoms = []

    mask_uint8 = mask.astype(np.uint8)

    shape_generator = shapes(mask_uint8, transform=transform)

    for geom, val in tqdm(
        shape_generator,
        desc=f"Vectorizing {class_name}",
        leave=False
    ):
        if val == 1:
            geoms.append(shape(geom))

    if len(geoms) == 0:
        print(f"⚠️ No geometries for class: {class_name}")
        continue

    gdf = gpd.GeoDataFrame(geometry=geoms, crs=crs)
    gdf["class"] = class_name

    geojson_path = os.path.join(output_dir, f"{class_name}.geojson")
    gdf.to_file(geojson_path, driver="GeoJSON")

    # -------------------------
    # 🖼️ DEBUG OVERLAY
    # -------------------------
    overlay = img.copy()
    alpha = 0.5

    highlight = np.zeros_like(img)
    highlight[:, :, 0] = 255

    overlay[mask] = (
        (1 - alpha) * overlay[mask] + alpha * highlight[mask]
    ).astype(np.uint8)

    overlay_path = os.path.join(output_dir, f"{class_name}_overlay.png")
    imageio.imwrite(overlay_path, overlay)


print("\n✅ Done processing")