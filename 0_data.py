import os
import math
import requests
from PIL import Image
from geopy.geocoders import Nominatim
from io import BytesIO
from tqdm import tqdm

TILE_SIZE = 256
ZOOM = 18

# -----------------------------
# 1. Get bbox
# -----------------------------
place_name = "El Harrach, Algeria"

geolocator = Nominatim(user_agent="osm_bbox_script")
location = geolocator.geocode(place_name)

bbox = location.raw['boundingbox']
south, north = float(bbox[0]), float(bbox[1])
west, east = float(bbox[2]), float(bbox[3])

print("BBox:", south, north, west, east)

# -----------------------------
# 2. Tile conversion
# -----------------------------
def latlon_to_tile(lat, lon, zoom):
    lat_rad = math.radians(lat)
    n = 2 ** zoom
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return x, y

# -----------------------------
# 3. Tile range
# -----------------------------
padding = 1

x_min, y_max = latlon_to_tile(south, west, ZOOM)
x_max, y_min = latlon_to_tile(north, east, ZOOM)

x_min -= padding
x_max += padding
y_min -= padding
y_max += padding

print("Tiles:", x_min, x_max, y_min, y_max)

# -----------------------------
# 4. Disk cache setup
# -----------------------------
cache_dir = f"data/tiles/{ZOOM}"
os.makedirs(cache_dir, exist_ok=True)

headers = {
    "User-Agent": "geo-tile-stitcher/1.0"
}

# -----------------------------
# 5. Download + cache tiles
# -----------------------------
tiles = {}

for x in tqdm(range(x_min, x_max + 1), desc="X tiles"):
    for y in range(y_min, y_max + 1):

        tile_path = f"{cache_dir}/{x}_{y}.png"

        # ---- LOAD FROM DISK IF EXISTS ----
        if os.path.exists(tile_path):
            try:
                img = Image.open(tile_path).convert("RGB")
                tiles[(x, y)] = img
                continue
            except Exception:
                pass  # corrupted file → re-download

        # ---- DOWNLOAD IF NOT CACHED ----
        url = f"https://tile.openstreetmap.org/{ZOOM}/{x}/{y}.png"

        try:
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                img = Image.open(BytesIO(r.content)).convert("RGB")

                # save to disk
                img.save(tile_path)

                tiles[(x, y)] = img
        except Exception:
            pass

# -----------------------------
# 6. Stitch tiles
# -----------------------------
width = (x_max - x_min + 1) * TILE_SIZE
height = (y_max - y_min + 1) * TILE_SIZE

map_img = Image.new("RGB", (width, height))

for (x, y), img in tiles.items():
    px = (x - x_min) * TILE_SIZE
    py = (y - y_min) * TILE_SIZE
    map_img.paste(img, (px, py))

# -----------------------------
# 7. Save final image
# -----------------------------
output_file = "el_harrach_highres_map.png"
map_img.save(output_file)

print("Saved:", output_file)
print("Tiles cached in:", cache_dir)