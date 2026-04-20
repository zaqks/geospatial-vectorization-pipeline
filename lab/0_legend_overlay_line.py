import pandas as pd
import numpy as np
import cv2
from tqdm import tqdm
from skimage.morphology import skeletonize

df = pd.read_csv("data/legend_class_geo.csv")
df = df[df["geometry"] == "line"]

img = cv2.imread("data/el_harrach_highres_map.png")
img_i16 = img.astype(np.int16)

tolerance = 1

def mask_to_1px_skeleton(mask):
    """
    Convert a binary mask to a 1-pixel-wide skeleton.
    """
    # Ensure binary (0/1)
    binary = mask.astype(np.uint8)

    # Skeletonize expects boolean
    skeleton = skeletonize(binary > 0)

    return skeleton.astype(np.uint8)

for i, row in tqdm(df.iterrows(), total=len(df), desc="Generating overlays"):
    hex_color = row["hex"].lstrip("#")
    rgb = np.array([int(hex_color[i:i+2], 16) for i in (0, 2, 4)], dtype=np.int16)
    bgr = rgb[::-1]

    # Create mask
    mask = np.all(np.abs(img_i16 - bgr) <= tolerance, axis=2)

    # 🔥 Convert to 1px skeleton
    skeleton = mask_to_1px_skeleton(mask)

    # Create result image
    result = img.copy()
    result[skeleton > 0] = (0, 0, 255)

    class_name = row["class"]
    class_name_safe = class_name.replace(" ", "_")

    cv2.imwrite(f"output/overlays/line/overlay_{i+1}_{class_name_safe}.png", result)