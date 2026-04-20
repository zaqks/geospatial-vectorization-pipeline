import numpy as np
import rasterio
from scipy.ndimage import binary_closing, binary_opening
from rasterio.features import shapes
import geopandas as gpd
from shapely.geometry import shape
import sys


# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
CLOSING_SIZE = 5
OPENING_SIZE = 2


# ─────────────────────────────────────────────
# HEX → RGB
# ─────────────────────────────────────────────
def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return (
        int(hex_color[0:2], 16),
        int(hex_color[2:4], 16),
        int(hex_color[4:6], 16),
    )


# ─────────────────────────────────────────────
# LOAD RASTER
# ─────────────────────────────────────────────
def load_raster(path):
    with rasterio.open(path) as src:
        img = src.read()
        transform = src.transform
        crs = src.crs

    img = np.transpose(img, (1, 2, 0))[:, :, :3]
    return img, transform, crs


# ─────────────────────────────────────────────
# CREATE MASK
# ─────────────────────────────────────────────
def create_mask(img, rgb, tol=1):
    target = np.array(rgb, dtype=np.int16)

    return np.all(
        np.abs(img.astype(np.int16) - target) <= tol,
        axis=2
    )


# ─────────────────────────────────────────────
# CLEAN MASK (gap filling)
# ─────────────────────────────────────────────
def clean(mask):
    closed = binary_closing(
        mask,
        structure=np.ones((CLOSING_SIZE, CLOSING_SIZE))
    )

    opened = binary_opening(
        closed,
        structure=np.ones((OPENING_SIZE, OPENING_SIZE))
    )

    return opened


# ─────────────────────────────────────────────
# VECTORIZE MASK
# ─────────────────────────────────────────────
def vectorize(mask, transform, crs):
    geoms = []

    for geom, val in shapes(mask.astype(np.uint8), mask=mask, transform=transform):
        if val == 1:
            geoms.append(shape(geom))

    gdf = gpd.GeoDataFrame(geometry=geoms, crs=crs)

    return gdf


# ─────────────────────────────────────────────
# MAIN PIPELINE
# ─────────────────────────────────────────────
def raster_to_geojson(raster_path, output_geojson, water_hex):

    print("Loading raster...")
    img, transform, crs = load_raster(raster_path)

    rgb = hex_to_rgb(water_hex)
    print(f"Target water RGB: {rgb}")

    print("Creating mask...")
    mask = create_mask(img, rgb)
    print(f"Initial pixels: {mask.sum()}")

    print("Cleaning mask...")
    mask = clean(mask)
    print(f"Cleaned pixels: {mask.sum()}")

    print("Vectorizing...")
    gdf = vectorize(mask, transform, crs)
    print(f"Polygons created: {len(gdf)}")

    # ─────────────────────────────
    # CLEAN GEOMETRY
    # ─────────────────────────────
    gdf = gdf[gdf.geometry.notnull()]
    gdf = gdf[~gdf.geometry.is_empty]

    # optional: remove tiny artifacts
    gdf["area"] = gdf.geometry.area
    gdf = gdf[gdf["area"] > 1].drop(columns=["area"])

    # ─────────────────────────────
    # SAVE GEOJSON
    # ─────────────────────────────
    print("Saving GeoJSON...")
    gdf.to_file(output_geojson, driver="GeoJSON")

    print(f"\n✅ DONE → {output_geojson}")

    return gdf


# ─────────────────────────────────────────────
# RUN
# ─────────────────────────────────────────────
if __name__ == "__main__":

    raster = sys.argv[1] if len(sys.argv) > 1 else "/home/zak/Desktop/projects/geospatial-vectorization-pipeline/lab/data/el_harrach_georef.tif"
    output = sys.argv[2] if len(sys.argv) > 2 else "water.geojson"
    water_hex = "#d5e8eb"  # your water color

    raster_to_geojson(raster, output, water_hex)