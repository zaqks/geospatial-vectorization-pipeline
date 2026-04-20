import os
import numpy as np
import pandas as pd
import cv2
import rasterio
import geopandas as gpd
from shapely.geometry import LineString
from tqdm import tqdm

# ─────────────────────────────
# CONFIG
# ─────────────────────────────
raster_path = "/home/zak/Desktop/projects/geospatial-vectorization-pipeline/lab/data/el_harrach_georef.tif"
output_dir = "output/vect/line2"
os.makedirs(output_dir, exist_ok=True)

COLOR_TOLERANCE = 1
MIN_LINE_LENGTH = 5  # removes noise


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
df = pd.read_csv("/home/zak/Desktop/projects/geospatial-vectorization-pipeline/lab/data/legend_class_geo.csv")
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

img = np.transpose(img, (1, 2, 0))[:, :, :3].astype(np.int16)


# ─────────────────────────────
# PROCESS
# ─────────────────────────────
for rgb, class_name in tqdm(color_map.items(), desc="Processing"):

    target = np.array(rgb, dtype=np.int16)

    # ── MASK (FAST VECTORISED) ──
    mask = np.all(np.abs(img - target) <= COLOR_TOLERANCE, axis=2).astype(np.uint8)

    if mask.sum() == 0:
        continue

    # ── CLEAN MASK (very light, avoids distortion) ──
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    # ── CONTOUR EXTRACTION (KEY STEP) ──
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

    # ── SAVE ──
    if not lines:
        continue

    gdf = gpd.GeoDataFrame(geometry=lines, crs=crs)
    gdf["class"] = class_name

    out_path = os.path.join(output_dir, f"{class_name}.geojson")
    gdf.to_file(out_path, driver="GeoJSON")

    print(f"Saved {class_name} → {len(lines)} lines")

print("\n✅ DONE")