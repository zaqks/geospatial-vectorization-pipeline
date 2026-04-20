import geopandas as gpd
import numpy as np
from shapely.geometry import LineString
from sklearn.cluster import KMeans

# -----------------------------
# PARAMETERS
# -----------------------------
MIN_LENGTH = 5

# -----------------------------
# EXTRACT MIDPOINTS
# -----------------------------
def get_midpoints(gdf):
    mids = []
    for geom in gdf.geometry:
        if geom is None or geom.length < MIN_LENGTH:
            continue

        coords = list(geom.coords)
        p1 = np.array(coords[0])
        p2 = np.array(coords[-1])

        mid = (p1 + p2) / 2
        mids.append(mid)

    return np.array(mids)


# -----------------------------
# MAIN
# -----------------------------
def process(input_file, output_file):
    gdf = gpd.read_file(input_file)

    pts = get_midpoints(gdf)

    if len(pts) < 10:
        print("Not enough data")
        return

    # -------------------------
    # 1. GLOBAL DIRECTION (stable)
    # -------------------------
    centroid = pts.mean(axis=0)
    cov = np.cov(pts - centroid, rowvar=False)
    eigvals, eigvecs = np.linalg.eig(cov)

    direction = eigvecs[:, np.argmax(eigvals)]
    normal = np.array([-direction[1], direction[0]])

    # -------------------------
    # 2. CLUSTER LEFT / RIGHT
    # -------------------------
    proj = (pts - centroid) @ normal
    labels = KMeans(n_clusters=2, random_state=0).fit(proj.reshape(-1,1)).labels_

    lines = []

    # -------------------------
    # 3. BUILD CLEAN LINES
    # -------------------------
    for i in range(2):
        cluster = pts[labels == i]

        if len(cluster) < 2:
            continue

        # sort ALONG railway direction (critical)
        t = (cluster - centroid) @ direction
        order = np.argsort(t)

        sorted_pts = cluster[order]

        # smooth a bit to remove zigzag
        sorted_pts = sorted_pts[::2]

        lines.append(LineString(sorted_pts))

    # -------------------------
    # OUTPUT
    # -------------------------
    out = gpd.GeoDataFrame(geometry=lines, crs=gdf.crs)
    out.to_file(output_file, driver="GeoJSON")

    print("DONE:", len(lines), "rails")
# -----------------------------
# RUN
# -----------------------------


if __name__ == "__main__":
    process("output/vect/line/railway.geojson", "output/vect/poly/output/vect/line/railway_clean.geojson")
