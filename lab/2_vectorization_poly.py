#!/usr/bin/env python
# coding: utf-8

# In[1]:


import os
import numpy as np
import pandas as pd
from tqdm import tqdm

import rasterio
from rasterio.features import shapes

import geopandas as gpd
from shapely.geometry import shape
from shapely.ops import unary_union
from shapely.validation import make_valid

from PIL import Image, ImageDraw


# In[2]:


# -------------------------
# CONFIG
# -------------------------
raster_path = "data/el_harrach_georef.tif"
output_dir = "output/vect/poly"
os.makedirs(output_dir, exist_ok=True)

tolerance = 1
EXPORT_TO_WGS84 = True 


# In[3]:


# -------------------------
# LEGEND
# -------------------------
df = pd.read_csv("data/legend_class_geo.csv")
df = df[df.geometry == "polygon"]

def hex_to_rgb(hex_color: str):
    hex_color = hex_color.lstrip("#")
    return (int(hex_color[0:2], 16),
            int(hex_color[2:4], 16),
            int(hex_color[4:6], 16))

color_class_map = {
    hex_to_rgb(row["hex"]): row["class"]
    for _, row in df.iterrows()
}

print(f"Loaded {len(color_class_map)} classes")


# In[4]:


# -------------------------
# READ RASTER
# -------------------------
with rasterio.open(raster_path) as src:
    img_data = src.read()
    transform = src.transform
    crs = src.crs
    # Prepare inverse transform for PNG drawing
    inv_transform = ~transform 

# Prepare image for PIL (H, W, C)
img_np = np.transpose(img_data, (1, 2, 0))[:, :, :3].astype(np.uint8)

print("\nRaster info:")
print("Shape:", img_np.shape)
print("CRS:", crs)


# In[5]:


# -------------------------
# HELPERS
# -------------------------
def explode_geom(geom):
    """Handle all geometry types safely"""
    if geom is None or geom.is_empty:
        return []
    if geom.geom_type == "Polygon":
        return [geom]
    if geom.geom_type == "MultiPolygon":
        return list(geom.geoms)
    if geom.geom_type == "GeometryCollection":
        out = []
        for g in geom.geoms:
            out.extend(explode_geom(g))
        return out
    return []


# In[6]:


# -------------------------
# PROCESS EACH CLASS
# -------------------------
for rgb, class_name in tqdm(color_class_map.items(), desc="Processing classes"):

    print(f"\nProcessing Class: {class_name} | RGB: {rgb}")

    target = np.array(rgb, dtype=np.int16)
    mask = np.all(np.abs(img_np.astype(np.int16) - target) <= tolerance, axis=2)

    if not np.any(mask):
        print("⚠️ Empty mask → skipping")
        continue

    mask_uint8 = mask.astype(np.uint8)

    # VECTORIZE (Results are in Map Coordinates)
    geoms = []
    for geom, val in shapes(mask_uint8, mask=mask_uint8, transform=transform):
        if val == 1:
            g = shape(geom)
            if not g.is_empty:
                geoms.append(g)

    if not geoms:
        continue

    # CLEAN GEOMETRIES
    cleaned = []
    for g in geoms:
        if not g.is_valid:
            g = make_valid(g)
        cleaned.extend(explode_geom(g))

    # MERGE & SAVE GEOJSON
    merged = unary_union(cleaned)
    gdf = gpd.GeoDataFrame(geometry=[merged], crs=crs)
    gdf["class"] = class_name

    if EXPORT_TO_WGS84:
        gdf = gdf.to_crs("EPSG:4326")

    geojson_path = os.path.join(output_dir, f"{class_name}.geojson")
    gdf.to_file(geojson_path, driver="GeoJSON")

    # -------------------------
    # PNG OVERLAY (FIXED COORDINATES)
    # -------------------------
    # Create RGBA overlay from the original image
    overlay = Image.fromarray(img_np).convert("RGBA")
    draw = ImageDraw.Draw(overlay)

    fill_color = (255, 0, 0, 120)  # Semi-transparent red
    outline_color = (255, 0, 0, 255)

    for g in cleaned:
        for poly in explode_geom(g):
            try:
                # Convert Map Coords (East/North) back to Pixel Coords (Col/Row)
                pixel_coords = [inv_transform * pt for pt in poly.exterior.coords]

                if len(pixel_coords) >= 3:
                    draw.polygon(pixel_coords, fill=fill_color, outline=outline_color)

                # Draw holes
                for interior in poly.interiors:
                    hole_coords = [inv_transform * pt for pt in interior.coords]
                    if len(hole_coords) >= 3:
                        draw.polygon(hole_coords, outline=outline_color)
            except Exception:
                continue

    png_path = os.path.join(output_dir, f"{class_name}.png")
    overlay.save(png_path)

print("\n✅ DONE: GeoJSONs and PNGs generated correctly.")


# In[ ]:




