import os
import numpy as np
import pandas as pd
import cv2
import rasterio
import geopandas as gpd
from shapely.geometry import LineString
from tqdm import tqdm
from PIL import Image, ImageDraw

# ─────────────────────────────
# CONFIG
# ─────────────────────────────
raster_path = "./data/el_harrach_georef.tif"
output_dir = "output/vect/line2"
os.makedirs(output_dir, exist_ok=True)

COLOR_TOLERANCE = 1
MIN_LINE_LENGTH = 5


# ─────────────────────────────
# HEX → RGB
# ─────────────────────────────
def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return (
        int(hex_color[0:2], 16),
        int(hex_color[2:4], 16),
        int(hex_color[4:6], 16),
    )


# ─────────────────────────────
# LOAD LEGEND
# ─────────────────────────────
df = pd.read_csv("./data/legend_class_geo.csv")
df = df[df.geometry == "line"]

color_map = {
    hex_to_rgb(row["hex"]): row["class"]
    for _, row in df.iterrows()
}

print(f"Loaded {len(color_map)} line classes")


# ─────────────────────────────
# LOAD RASTER
# ─────────────────────────────
with rasterio.open(raster_path) as src:
    img = src.read()
    transform = src.transform
    crs = src.crs
    inv_transform = ~transform  # for pixel-space drawing if needed

img = np.transpose(img, (1, 2, 0))[:, :, :3].astype(np.int16)


# ─────────────────────────────
# PROCESS
# ─────────────────────────────
for rgb, class_name in tqdm(color_map.items(), desc="Processing"):

    target = np.array(rgb, dtype=np.int16)

    # ── MASK ──
    mask = np.all(np.abs(img - target) <= COLOR_TOLERANCE, axis=2).astype(np.uint8)

    if mask.sum() == 0:
        continue

    # ── CLEAN MASK ──
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    # ── CONTOURS ──
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)

    lines = []

    for cnt in contours:

        if len(cnt) < MIN_LINE_LENGTH:
            continue

        coords = []

        for pt in cnt:
            x, y = pt[0]

            # raster → geo transform
            X, Y = transform * (x, y)
            coords.append((X, Y))

        if len(coords) > 2:
            lines.append(LineString(coords))

    # ─────────────────────────────
    # SAVE GEOJSON
    # ─────────────────────────────
    if not lines:
        continue

    gdf = gpd.GeoDataFrame(geometry=lines, crs=crs)
    gdf["class"] = class_name

    geojson_path = os.path.join(output_dir, f"{class_name}.geojson")
    gdf.to_file(geojson_path, driver="GeoJSON")

    print(f"Saved {class_name} → {len(lines)} lines")

    # ─────────────────────────────
    # PNG OVERLAY (ADDED FEATURE)
    # ─────────────────────────────
    overlay = Image.fromarray(img.astype(np.uint8)).convert("RGBA")
    draw = ImageDraw.Draw(overlay)

    line_color = (255, 0, 0, 255)  # red

    for cnt in contours:
        if len(cnt) < MIN_LINE_LENGTH:
            continue

        pixel_line = [(pt[0][0], pt[0][1]) for pt in cnt]
        draw.line(pixel_line, fill=line_color, width=2)

    png_path = os.path.join(output_dir, f"{class_name}.png")
    overlay.save(png_path)

    print(f"Saved overlay PNG → {png_path}")

print("\n✅ DONE")