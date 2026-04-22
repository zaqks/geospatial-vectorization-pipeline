# %%
# -----------------------------
# Imports
# -----------------------------
import os
import math
import requests
from PIL import Image
from geopy.geocoders import Nominatim
from io import BytesIO
from tqdm import tqdm
# %%

# -----------------------------
# 1. Configuration
# -----------------------------
TILE_SIZE = 256
ZOOM = 18
place_name = "El Harrach, Algeria"
output_file = "./data/el_harrach_highres_map.png"
cache_dir = f"data/tiles/{ZOOM}"
os.makedirs(cache_dir, exist_ok=True)
# %%

# -----------------------------
# 2. Coordinate Conversion Functions
# -----------------------------

## Convert latitude/longitude to tile indices
def latlon_to_tile(lat, lon, zoom):
    lat_rad = math.radians(lat)
    n = 2.0 ** zoom
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return x, y

## Convert tile indices to lat/lon (top-left corner)
def tile_to_latlon(x, y, zoom):
    n = 2.0 ** zoom
    lon_deg = x / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
    lat_deg = math.degrees(lat_rad)
    return lat_deg, lon_deg
# %%

# -----------------------------
# 3. Get Geocoded Bounding Box
# -----------------------------
geolocator = Nominatim(user_agent="osm_bbox_script")
location = geolocator.geocode(place_name)

bbox = location.raw['boundingbox']
south, north, west, east = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])

print("BBox:", south, north, west, east)
# %%

# -----------------------------
# 4. Calculate Tile Range
# -----------------------------
padding = 1

x_start, y_end = latlon_to_tile(south, west, ZOOM)
x_end, y_start = latlon_to_tile(north, east, ZOOM)

x_min, x_max = x_start - padding, x_end + padding
y_min, y_max = y_start - padding, y_end + padding

print("Tile range:")
print(x_min, x_max, y_min, y_max)
# %%

# -----------------------------
# 5. Download Tiles
# -----------------------------
headers = {"User-Agent": "geo-tile-stitcher/1.0"}
tiles = {}

for x in tqdm(range(x_min, x_max + 1), desc="Downloading tiles"):
    for y in range(y_min, y_max + 1):

        tile_path = f"{cache_dir}/{x}_{y}.png"

        ## Load from cache
        if os.path.exists(tile_path):
            try:
                tiles[(x, y)] = Image.open(tile_path).convert("RGB")
                continue
            except:
                pass

        ## Download tile
        url = f"https://basemaps.cartocdn.com/rastertiles/voyager_nolabels/{ZOOM}/{x}/{y}.png"

        try:
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                img = Image.open(BytesIO(r.content)).convert("RGB")
                img.save(tile_path)
                tiles[(x, y)] = img
        except:
            pass

print(f"Downloaded tiles: {len(tiles)}")
# %%

# -----------------------------
# 6. Stitch Tiles
# -----------------------------
width = (x_max - x_min + 1) * TILE_SIZE
height = (y_max - y_min + 1) * TILE_SIZE
map_img = Image.new("RGB", (width, height))

for (x, y), img in tiles.items():
    map_img.paste(img, ((x - x_min) * TILE_SIZE, (y - y_min) * TILE_SIZE))

map_img.save(output_file)
print("Saved image:", output_file)
# %%

# -----------------------------
# 7. Compute Final Georeferenced Bounds
# -----------------------------
final_north, final_west = tile_to_latlon(x_min, y_min, ZOOM)
final_south, final_east = tile_to_latlon(x_max + 1, y_max + 1, ZOOM)

print("-" * 30)
print("STITCHED IMAGE BOUNDS (EPSG:4326):")
print(f"North: {final_north}")
print(f"South: {final_south}")
print(f"West:  {final_west}")
print(f"East:  {final_east}")
print("-" * 30)