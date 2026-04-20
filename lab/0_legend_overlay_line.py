#!/usr/bin/env python
# coding: utf-8

import os
import cv2
import numpy as np
import pandas as pd
from tqdm import tqdm

# -------------------------
# Load data
# -------------------------
df = pd.read_csv("data/legend_class_geo.csv")
df = df[df["geometry"] == "line"].reset_index(drop=True)

img = cv2.imread("data/el_harrach_highres_map.png")

if img is None:
    raise FileNotFoundError("Image not found")

tolerance = 1
thickness = 10
radius = max(1, thickness // 2)

os.makedirs("output/overlays/line", exist_ok=True)

# -------------------------
# FAST skeleton (no contrib OpenCV)
# Zhang-Suen / morphological thinning fallback
# -------------------------
def skeletonize_opencv(binary_mask):
    img = binary_mask.copy().astype(np.uint8)
    skel = np.zeros(img.shape, np.uint8)

    kernel = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))

    while True:
        eroded = cv2.erode(img, kernel)
        temp = cv2.dilate(eroded, kernel)
        temp = cv2.subtract(img, temp)
        skel = cv2.bitwise_or(skel, temp)
        img = eroded

        if cv2.countNonZero(img) == 0:
            break

    return skel


# -------------------------
# Fast dilation
# -------------------------
def thicken(mask, radius):
    kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE,
        (radius * 2 + 1, radius * 2 + 1)
    )
    return cv2.dilate(mask, kernel)


# -------------------------
# Main loop
# -------------------------
for i, row in tqdm(df.iterrows(), total=len(df), desc="Generating overlays"):

    # Convert hex → BGR
    hex_color = row["hex"].lstrip("#")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)

    color = np.array([b, g, r], dtype=np.uint8)

    # -------------------------
    # Fast mask extraction
    # -------------------------
    lower = np.clip(color - tolerance, 0, 255)
    upper = np.clip(color + tolerance, 0, 255)

    mask = cv2.inRange(img, lower, upper)

    # Skip empty results (big speed win)
    if cv2.countNonZero(mask) == 0:
        continue

    # -------------------------
    # Skeletonize
    # -------------------------
    skeleton = skeletonize_opencv(mask)

    # -------------------------
    # Thicken
    # -------------------------
    thick = thicken(skeleton, radius)

    # -------------------------
    # Apply overlay
    # -------------------------
    result = img.copy()
    result[thick > 0] = (0, 0, 255)

    # -------------------------
    # Save
    # -------------------------
    class_name = row["class"].replace(" ", "_")
    out_path = f"output/overlays/line/overlay_{i+1}_{class_name}.png"

    cv2.imwrite(out_path, result)