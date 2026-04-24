#!/usr/bin/env python
# coding: utf-8

# %%


import pandas as pd

df = pd.read_csv("data/legend_class_geo.csv")
df = df[df["geometry"] == "polygon"]
df.head()


# %%

import os
os.makedirs("output/overlays/poly", exist_ok=True)


# %%


import numpy as np
import cv2
from tqdm import tqdm

img = cv2.imread("data/el_harrach_highres_map.png")
img_i16 = img.astype(np.int16)

tolerance = 1
# overlays = []

for i, row in tqdm(df.iterrows(), total=len(df), desc="Generating overlays"):
    hex_color = row["hex"].lstrip("#")
    rgb = np.array([int(hex_color[i:i+2], 16) for i in (0, 2, 4)], dtype=np.int16)
    bgr = rgb[::-1]  # convert to BGR for OpenCV

    mask = np.all(np.abs(img_i16 - bgr) <= tolerance, axis=2)

    result = img.copy()
    result[mask] = (0, 0, 255)

    # overlays.append(result)

    class_name = row["class"]
    class_name_safe = class_name.replace(" ", "_")

    cv2.imwrite(f"output/overlays/poly/overlay_{i+1}_{class_name_safe}.png", result)

