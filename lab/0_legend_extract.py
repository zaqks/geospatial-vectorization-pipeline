#!/usr/bin/env python
# coding: utf-8

# %%


from PIL import Image
import numpy as np
import polars as pl
import csv


def rgb_to_hex(rgb):
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def extract_unique_colors_polars(image_path, resize=None):
    img = Image.open(image_path).convert("RGB")

    if resize:
        img = img.resize(resize)

    pixels = np.array(img).reshape(-1, 3)

    # Convert to Polars DataFrame
    df = pl.DataFrame({
        "r": pixels[:, 0],
        "g": pixels[:, 1],
        "b": pixels[:, 2],
    })

    # Group by exact RGB values
    result = (
        df.group_by(["r", "g", "b"])
        .agg(pl.len().alias("count"))
        .with_columns([
            (pl.col("count") / pl.col("count").sum() * 100).alias("percentage")
        ])
        .sort("count", descending=True)
    )

    return result


# %%


res = extract_unique_colors_polars(
    "data/el_harrach_highres_map.png",
    resize=None
)

# top = res.head(15)
top = res


# %%


# Export CSV
with open("data/legend.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["hex", "percentage"])

    for row in top.iter_rows(named=True):
        if row["percentage"] < 0.1:
            break

        hex_color = rgb_to_hex((row["r"], row["g"], row["b"]))
        writer.writerow([hex_color, row["percentage"]])

