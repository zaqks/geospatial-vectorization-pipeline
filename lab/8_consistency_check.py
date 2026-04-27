#!/usr/bin/env python
# coding: utf-8
import os
import warnings

warnings.filterwarnings("ignore")

import numpy as np
import geopandas as gpd
import osmnx as ox
from shapely.strtree import STRtree
from tqdm import tqdm


# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
PLACE = "El Harrach, Algeria"
TARGET_CRS = "EPSG:3857"
LINE_BUFFER_M = 3

PREDICTED = {
    "building": "output/vect/poly/building.geojson",
    "water": "output/vect/poly/water.geojson",
    "residential area": "output/vect/poly/residential area.geojson",
    "grass": "output/vect/poly/grass.geojson",
    "autoroute": "output/vect/line/autoroute.geojson",
    "route_nationale": "output/vect/line/route_nationale.geojson",
    "street": "output/vect/line/street.geojson",
    "railway": "output/vect/line/railway.geojson",
}

LINE_CLASSES = {"autoroute", "route_nationale", "street", "railway"}


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def load_pred(path, bbox=None):
    if not os.path.exists(path):
        return None

    gdf = gpd.read_file(path)
    if gdf.empty:
        return None

    if gdf.crs is None:
        gdf = gdf.set_crs(TARGET_CRS)
    else:
        gdf = gdf.to_crs(TARGET_CRS)

    gdf = gdf[gdf.geometry.notnull() & ~gdf.geometry.is_empty]

    if bbox is not None:
        gdf = gpd.clip(gdf, bbox)

    return gdf


def build_tree(geoms):
    geoms = list(geoms)
    if not geoms:
        return None, []
    return STRtree(geoms), geoms


# ─────────────────────────────────────────────
# CORRECT METRICS (SYMMETRIC)
# ─────────────────────────────────────────────
def symmetric_match_metrics(pred_gdf, gt_gdf):
    if pred_gdf is None or gt_gdf is None:
        return 0.0, 0.0, 0.0

    if pred_gdf.empty or gt_gdf.empty:
        return 0.0, 0.0, 0.0

    pred_geoms = list(pred_gdf.geometry)
    gt_geoms = list(gt_gdf.geometry)

    pred_tree, pred_list = build_tree(pred_geoms)
    gt_tree, gt_list = build_tree(gt_geoms)

    if pred_tree is None or gt_tree is None:
        return 0.0, 0.0, 0.0

    # GT → Pred (recall)
    gt_hits = 0
    for g in gt_list:
        if g.is_empty:
            continue
        idxs = pred_tree.query(g)
        if any(g.intersects(pred_list[i]) for i in idxs):
            gt_hits += 1

    # Pred → GT (precision)
    pred_hits = 0
    for p in pred_list:
        if p.is_empty:
            continue
        idxs = gt_tree.query(p)
        if any(p.intersects(gt_list[i]) for i in idxs):
            pred_hits += 1

    recall = gt_hits / len(gt_list) if gt_list else 0.0
    precision = pred_hits / len(pred_list) if pred_list else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    return precision, recall, f1


# ─────────────────────────────────────────────
# STEP 1 — BOUNDARY
# ─────────────────────────────────────────────
print("=" * 60)
print(" FAST OSM EVALUATION (CORRECT METRICS)")
print("=" * 60)

boundary = ox.geocode_to_gdf(PLACE).to_crs(TARGET_CRS)
bbox = boundary.geometry.iloc[0]


# ─────────────────────────────────────────────
# STEP 2 — OSM DATA
# ─────────────────────────────────────────────
print("\n[1/3] Loading OSM ground truth...")

gt = {}


def fetch(tags, name):
    gdf = ox.features_from_place(PLACE, tags)
    gdf = gdf.to_crs(TARGET_CRS)
    gdf = gdf[gdf.geometry.notnull() & ~gdf.geometry.is_empty]
    gdf = gpd.clip(gdf, bbox)
    gt[name] = gdf
    print(f"{name:<18}: {len(gdf)}")


fetch({"building": True}, "building")
fetch({"natural": ["water", "wetland"], "waterway": True}, "water")
fetch({"landuse": ["residential"]}, "residential area")
fetch({"landuse": ["grass", "meadow", "park"], "natural": "grassland"}, "grass")


# roads
G = ox.graph_from_place(PLACE, network_type="drive")
edges = ox.graph_to_gdfs(G, nodes=False).to_crs(TARGET_CRS)

highway_map = {
    "autoroute": ["motorway", "trunk"],
    "route_nationale": ["primary", "secondary"],
    "street": ["tertiary", "residential", "service"],
}

for k, v in highway_map.items():
    subset = edges[edges["highway"].astype(str).isin(v)]
    subset = gpd.clip(subset, bbox)
    gt[k] = subset
    print(f"{k:<18}: {len(subset)}")

fetch({"railway": ["rail", "tram", "subway"]}, "railway")


# ─────────────────────────────────────────────
# STEP 3 — EVALUATION
# ─────────────────────────────────────────────
print("\n[2/3] Computing metrics...\n")

results = []

for cls, path in tqdm(PREDICTED.items(), desc="Classes"):
    pred = load_pred(path, bbox)
    is_line = cls in LINE_CLASSES

    if pred is None:
        results.append((cls, "MISSING PRED", 0, 0, 0))
        continue

    if cls not in gt:
        results.append((cls, "MISSING GT", 0, 0, 0))
        continue

    gt_gdf = gt[cls]

    # buffer lines for fairness
    if is_line:
        pred = pred.copy()
        gt_gdf = gt_gdf.copy()
        pred["geometry"] = pred.buffer(LINE_BUFFER_M)
        gt_gdf["geometry"] = gt_gdf.buffer(LINE_BUFFER_M)

    precision, recall, f1 = symmetric_match_metrics(pred, gt_gdf)
    results.append((cls, "OK", precision, recall, f1))


# ─────────────────────────────────────────────
# STEP 4 — REPORT
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print(f"{'CLASS':<20} {'PREC':>8} {'REC':>8} {'F1':>8}")
print("-" * 60)

prec_list, rec_list, f1_list = [], [], []

for cls, status, p, r, f in results:
    if status != "OK":
        print(f"{cls:<20} {status}")
        continue

    prec_list.append(p)
    rec_list.append(r)
    f1_list.append(f)
    print(f"{cls:<20} {p*100:7.1f}% {r*100:7.1f}% {f*100:7.1f}%")

print("-" * 60)

if prec_list:
    print(
        f"{'AVERAGE':<20} "
        f"{np.mean(prec_list)*100:7.1f}% "
        f"{np.mean(rec_list)*100:7.1f}% "
        f"{np.mean(f1_list)*100:7.1f}%"
    )
print("=" * 60)


print("\n")
print("PRECISION (PREC):")
print("Measures how many of the predicted positive results are actually correct.")
print("It focuses on avoiding false positives.\n")

print("RECALL (REC):")
print("Measures how many of the actual positive cases were correctly found.")
print("It focuses on avoiding false negatives.\n")

print("F1 SCORE (F1):")
print("The harmonic mean of precision and recall.")
print("It balances both precision and recall into a single metric.\n")

print("Done.")