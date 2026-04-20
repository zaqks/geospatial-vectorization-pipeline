import os
import numpy as np
import pandas as pd
import cv2
import rasterio
import geopandas as gpd
from shapely.geometry import LineString
from tqdm import tqdm
from skimage.morphology import medial_axis
from PIL import Image, ImageDraw

# ─────────────────────────────
# CONFIG
# ─────────────────────────────
raster_path = "/home/zak/Desktop/projects/geospatial-vectorization-pipeline/lab/data/el_harrach_georef.tif"
legend_path = "/home/zak/Desktop/projects/geospatial-vectorization-pipeline/lab/data/legend_class_geo.csv"
output_dir = "output/vect/skeleton_from_contours"
os.makedirs(output_dir, exist_ok=True)

COLOR_TOLERANCE = 1
MIN_LINE_LENGTH = 5


# ─────────────────────────────
# HELPERS
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
df = pd.read_csv(legend_path)
df = df[df.geometry == "line"]

color_map = {
    hex_to_rgb(row["hex"]): row["class"]
    for _, row in df.iterrows()
}

print(f"Loaded {len(color_map)} classes")


# ─────────────────────────────
# LOAD RASTER
# ─────────────────────────────
with rasterio.open(raster_path) as src:
    img = src.read()
    transform = src.transform
    crs = src.crs

img = np.transpose(img, (1, 2, 0))[:, :, :3].astype(np.int16)


# ─────────────────────────────
# PROCESS EACH CLASS
# ─────────────────────────────
for rgb, class_name in tqdm(color_map.items(), desc="Processing"):

    target = np.array(rgb, dtype=np.int16)

    # ── 1. MASK ──
    mask = np.all(np.abs(img - target) <= COLOR_TOLERANCE, axis=2).astype(np.uint8)

    if mask.sum() == 0:
        continue

    # ── 2. FIND CONTOURS ──
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)

    if not contours:
        continue

    # ── 3. FILL CONTOURS → CLEAN BINARY REGION ──
    filled = np.zeros_like(mask, dtype=np.uint8)
    cv2.drawContours(filled, contours, -1, 1, thickness=cv2.FILLED)

    # ── 4. SKELETONIZE FILLED REGION ──
    skeleton, _ = medial_axis(filled.astype(bool), return_distance=True)

    # ── 5. VECTORIZE SKELETON ──
    visited = skeleton.copy()
    h, w = skeleton.shape
    lines = []

    for y in range(h):
        for x in range(w):
            if not skeleton[y, x] or not visited[y, x]:
                continue

            coords = []
            cy, cx = y, x

            while True:
                coords.append((cx, cy))
                visited[cy, cx] = False

                found = False
                for dy in [-1, 0, 1]:
                    for dx in [-1, 0, 1]:
                        ny, nx = cy + dy, cx + dx
                        if (
                            0 <= ny < h and 0 <= nx < w
                            and skeleton[ny, nx]
                            and visited[ny, nx]
                        ):
                            cy, cx = ny, nx
                            found = True
                            break
                    if found:
                        break

                if not found:
                    break

            if len(coords) > MIN_LINE_LENGTH:
                geo_coords = [transform * (x, y) for x, y in coords]
                lines.append(LineString(geo_coords))

    if not lines:
        continue

    # ── 6. SAVE GEOJSON ──
    gdf = gpd.GeoDataFrame(geometry=lines, crs=crs)
    gdf["class"] = class_name

    geojson_path = os.path.join(output_dir, f"{class_name}.geojson")
    gdf.to_file(geojson_path, driver="GeoJSON")

    print(f"Saved {class_name} → {len(lines)} lines")

    # ─────────────────────────────
    # 7. PNG OVERLAY FROM GEOJSON
    # ─────────────────────────────
    overlay = Image.fromarray(img.astype(np.uint8)).convert("RGBA")
    draw = ImageDraw.Draw(overlay)

    for line in lines:
        pixel_coords = [
            (~transform) * (x, y) for x, y in line.coords
        ]
        pixel_coords = [(int(x), int(y)) for x, y in pixel_coords]

        draw.line(pixel_coords, fill=(255, 0, 0, 255), width=2)

    png_path = os.path.join(output_dir, f"{class_name}.png")
    overlay.save(png_path)

    print(f"Saved PNG → {png_path}")

print("\n✅ DONE")
