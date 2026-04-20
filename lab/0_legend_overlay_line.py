#!/usr/bin/env python
# coding: utf-8

import pandas as pd
import numpy as np
import cv2
from tqdm import tqdm
from skimage.morphology import skeletonize, dilation, disk

df = pd.read_csv("data/legend_class_geo.csv")
df = df[df["geometry"] == "line"]

img = cv2.imread("data/el_harrach_highres_map.png")
img_i16 = img.astype(np.int16)

tolerance = 1
thickness = 10

import os

os.makedirs("output/overlays/line", exist_ok=True)


def mask_to_1px_skeleton(mask):
    binary = mask.astype(np.uint8)
    skeleton = skeletonize(binary > 0)
    return skeleton.astype(np.uint8)


def thicken_skeleton(skel, thickness):
    radius = max(1, thickness // 2)
    return dilation(skel, disk(radius)).astype(np.uint8)


for i, row in tqdm(df.iterrows(), total=len(df), desc="Generating overlays"):
    hex_color = row["hex"].lstrip("#")
    rgb = np.array([int(hex_color[i : i + 2], 16) for i in (0, 2, 4)], dtype=np.int16)
    bgr = rgb[::-1]

    mask = np.all(np.abs(img_i16 - bgr) <= tolerance, axis=2)

    skeleton = mask_to_1px_skeleton(mask)

    thick_skeleton = thicken_skeleton(skeleton, thickness)

    result = img.copy()
    result[thick_skeleton > 0] = (0, 0, 255)

    class_name = row["class"]
    class_name_safe = class_name.replace(" ", "_")

    cv2.imwrite(f"output/overlays/line/overlay_{i+1}_{class_name_safe}.png", result)
