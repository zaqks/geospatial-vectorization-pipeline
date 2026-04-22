#!/usr/bin/env python
# coding: utf-8

# In[1]:


import math
import numpy as np
from PIL import Image
import rasterio
from rasterio.transform import from_bounds


# In[2]:


# -----------------------------
# Input Parameters
# -----------------------------
input_image = "./data/el_harrach_highres_map.png"
output_tif = "./data/el_harrach_georef.tif"
place_name = "El Harrach, Algeria"

# Bounding box (EPSG:4326 - lat/lon)
south, north, west, east = 36.6931181, 36.7309185, 3.1148535, 3.1639197
# 36.6931181, 3.1148535, 36.7309185, 3.1639197

# mini map: 
# 36.7120183, 3.1148535, 36.7309185, 3.1393866

# In[3]:


# -----------------------------
# Web Mercator Conversion
# -----------------------------
R = 6378137.0  # Earth radius in meters (Web Mercator)

def lon_to_x(lon):
    return R * math.radians(lon)

def lat_to_y(lat):
    return R * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))

min_x = lon_to_x(west)
max_x = lon_to_x(east)
min_y = lat_to_y(south)
max_y = lat_to_y(north)


# In[5]:


# -----------------------------
# Load Image
# -----------------------------
img = Image.open(input_image).convert("RGB")
img_np = np.array(img)
height, width, bands = img_np.shape


# In[6]:


# -----------------------------
# Affine Transform
# -----------------------------
transform = from_bounds(
    min_x, min_y,
    max_x, max_y,
    width,
    height
)


# In[7]:


# -----------------------------
# Write GeoTIFF
# -----------------------------
with rasterio.open(
    output_tif,
    "w",
    driver="GTiff",
    height=height,
    width=width,
    count=3,
    dtype=img_np.dtype,
    crs="EPSG:3857",
    transform=transform,
    compress="DEFLATE",   # better compression than LZW
    predictor=2,          # important for RGB imagery
    tiled=True,
    blockxsize=256,
    blockysize=256
) as dst:
    dst.write(img_np[:, :, 0], 1)
    dst.write(img_np[:, :, 1], 2)
    dst.write(img_np[:, :, 2], 3)

print("Saved GeoTIFF:", output_tif)


# In[ ]:




