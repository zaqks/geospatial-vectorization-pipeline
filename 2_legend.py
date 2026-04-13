import cv2
import numpy as np
from sklearn.cluster import KMeans


def rgb_to_hex(rgb):
    return '#{:02x}{:02x}{:02x}'.format(int(rgb[0]), int(rgb[1]), int(rgb[2]))


def extract_colors(image_path, num_colors=12, resize_width=600):
    # Load image
    img = cv2.imread(image_path)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    # Resize for speed (keeps aspect ratio)
    h, w = img.shape[:2]
    scale = resize_width / float(w)
    img = cv2.resize(img, (resize_width, int(h * scale)))

    # Flatten pixels
    pixels = img.reshape((-1, 3))

    # Optional: remove near-white background (common in OSM maps)
    pixels = pixels[~np.all(pixels > 240, axis=1)]

    # KMeans clustering
    kmeans = KMeans(n_clusters=num_colors, random_state=42, n_init=10)
    kmeans.fit(pixels)

    colors = kmeans.cluster_centers_

    # Convert to hex
    hex_colors = [rgb_to_hex(c) for c in colors]

    return hex_colors


import csv

if __name__ == "__main__":
    image_path = "data/el_harrach_georef.tif"  # your scanned OSM image
    colors = extract_colors(image_path, num_colors=15)

    print("Extracted colors:")

    output_csv = "output/legend.csv"

    with open(output_csv, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        
        # header
        writer.writerow(["hex", "label"])

        for c in colors:
            print(c)
            writer.writerow([c, ""])
    
    print(f"\nSaved to {output_csv}")