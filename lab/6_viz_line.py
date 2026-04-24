import os
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from PIL import Image
from rasterio.features import rasterize
from tqdm import tqdm


CSV_PATH = "data/legend_class_geo.csv"
TIFF_PATH = "data/el_harrach_georef.tif"
GEOJSON_DIR = Path("output/vect/line")
OUTPUT_DIR = Path("output/viz")
TARGET_CRS = "EPSG:3857"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def save_png(arr: np.ndarray, path: Path):
    Image.fromarray(arr).save(path, format="PNG", optimize=False)


# -----------------------
# Load class → value map
# -----------------------
df = pd.read_csv(CSV_PATH).dropna(subset=["class", "z"])
z_map = dict(zip(df["class"].astype(str), df["z"].astype(int)))

# -----------------------
# Load raster reference
# -----------------------
with rasterio.open(TIFF_PATH) as src:
    transform = src.transform
    crs = src.crs
    h, w = src.height, src.width

    if src.count >= 3:
        rgb_base = np.transpose(src.read([1, 2, 3]), (1, 2, 0)).astype(np.uint8)
    else:
        band = src.read(1).astype(np.uint8)
        rgb_base = np.stack([band, band, band], axis=-1)

if str(crs) != TARGET_CRS:
    raise ValueError(f"Expected raster CRS {TARGET_CRS}, got {crs}")

# -----------------------
# Load ALL GeoJSON once
# -----------------------
geojson_map = {
    p.stem: gpd.read_file(p)
    for p in GEOJSON_DIR.glob("*.geojson")
}

# -----------------------
# Build ONE raster (key optimization)
# -----------------------
shapes = []

for cls_name, z in z_map.items():
    gdf = geojson_map.get(cls_name)
    if gdf is None:
        continue

    gdf = gdf[gdf.geometry.notnull() & ~gdf.geometry.is_empty]
    if gdf.empty:
        continue

    if gdf.crs is None:
        raise ValueError(f"{cls_name}.geojson has no CRS")
    if str(gdf.crs) != TARGET_CRS:
        raise ValueError(f"{cls_name}.geojson CRS must be {TARGET_CRS}, got {gdf.crs}")

    shapes.extend((geom, z) for geom in gdf.geometry)

print(f"Rasterizing {len(shapes)} geometries...")

class_raster = rasterize(
    shapes,
    out_shape=(h, w),
    transform=transform,
    fill=0,
    dtype=np.uint16,   # important: supports many classes
)

# -----------------------
# Generate outputs per class (fast NumPy ops)
# -----------------------
for cls_name, z in tqdm(z_map.items()):

    mask = (class_raster == z)
    if not mask.any():
        continue

    # RGBA mask
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    rgba[mask] = [255, 0, 0, 255]

    # RGB overlay
    overlay = rgb_base.copy()
    overlay[mask] = [255, 0, 0]

    save_png(rgba, OUTPUT_DIR / f"{z}_{cls_name}_mask.png")
    save_png(overlay, OUTPUT_DIR / f"{z}_{cls_name}_overlay.png")
