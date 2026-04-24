# %%
import os
import cv2
import numpy as np
import pandas as pd
from tqdm import tqdm
# %%
# -------------------------
# Setup & Config
# %%
# -------------------------
df = pd.read_csv("data/legend_class_geo.csv")
df = df[df["geometry"] == "line"].reset_index(drop=True)

img = cv2.imread("data/el_harrach_highres_map.png")
if img is None:
    raise FileNotFoundError("Input image not found in data/el_harrach_highres_map.png")

# Convert to int16 to prevent overflow during subtraction
img_i16 = img.astype(np.int16)

TOLERANCE = 1
# This adds a slight thickness to the found lines so they are visible over the map
LINE_THICKNESS_BOOST = 10 

output_dir = "output/overlays/line"
os.makedirs(output_dir, exist_ok=True)

print(f"Processing {len(df)} line classes...")
# %%
# -------------------------
# Main Processing Loop
# %%
# -------------------------
for i, row in tqdm(df.iterrows(), total=len(df), desc="Generating line overlays"):
    class_name = row["class"]
    hex_color = row["hex"].lstrip("#")
    
    # Convert hex to BGR (OpenCV format)
    rgb = [int(hex_color[j:j+2], 16) for j in (0, 2, 4)]
    bgr = np.array(rgb[::-1], dtype=np.int16)

    # 1. Precise Color Masking (Polygon-style logic)
    # Checks if the absolute difference between pixel and target color is within tolerance
    mask = np.all(np.abs(img_i16 - bgr) <= TOLERANCE, axis=2).astype(np.uint8) * 255

    if cv2.countNonZero(mask) == 0:
        continue

    # 2. Morphological Closing
    # Fills small gaps in the lines for a cleaner overlay
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    # 3. Optional: Dilate if you want the overlay to be more prominent
    if LINE_THICKNESS_BOOST > 0:
        boost_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (LINE_THICKNESS_BOOST * 2 + 1, ++1))
        mask = cv2.dilate(mask, boost_kernel)

    # 4. Create Overlay
    # Copy original image and paint the detected mask bright RED (BGR: 0, 0, 255)
    result = img.copy()
    result[mask > 0] = (0, 0, 255)

    # 5. Save
    safe_name = class_name.replace(" ", "_").replace("/", "-")
    out_path = os.path.join(output_dir, f"overlay_{i+1}_{safe_name}.png")
    cv2.imwrite(out_path, result)

print(f"\nDone! Overlays saved to {output_dir}")