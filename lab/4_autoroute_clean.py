import geopandas as gpd
import networkx as nx
from shapely.geometry import LineString, MultiLineString, Point
from shapely.ops import snap
import numpy as np


# ─────────────────────────────────────────────
# CONFIG (SAFE DEFAULTS)
# ─────────────────────────────────────────────
SNAP_TOLERANCE = 2.0       # meters (EPSG:3857)
MIN_EDGE_LENGTH = 5.0
MAX_CONNECTOR_BETWEEN_PARALLELS = 0.15  # graph shortcut ratio threshold


# ─────────────────────────────────────────────
# UTILITIES
# ─────────────────────────────────────────────
def extract_lines(gdf):
    lines = []
    for g in gdf.geometry:
        if isinstance(g, LineString):
            lines.append(g)
        elif isinstance(g, MultiLineString):
            lines.extend(list(g.geoms))
    return lines


def angle(line):
    x1, y1 = line.coords[0]
    x2, y2 = line.coords[-1]
    return np.degrees(np.arctan2(y2 - y1, x2 - x1)) % 180


def snap_point(p):
    return (round(p.x / SNAP_TOLERANCE), round(p.y / SNAP_TOLERANCE))


# ─────────────────────────────────────────────
# BUILD ROAD GRAPH
# ─────────────────────────────────────────────
def build_graph(lines):

    G = nx.Graph()

    for i, line in enumerate(lines):

        if line.length < MIN_EDGE_LENGTH:
            continue

        coords = list(line.coords)
        start = snap_point(Point(coords[0]))
        end = snap_point(Point(coords[-1]))

        G.add_edge(start, end, geometry=line, length=line.length, id=i)

    return G


# ─────────────────────────────────────────────
# DETECT CONNECTOR EDGES (CORE LOGIC)
# ─────────────────────────────────────────────
def is_connector_edge(G, u, v, data):

    # degree-based logic
    if G.degree[u] > 2 and G.degree[v] > 2:
        return True

    # shortcut detection: if edge is too short compared to neighborhood
    neighbors_u = list(G.neighbors(u))
    neighbors_v = list(G.neighbors(v))

    if len(neighbors_u) > 1 and len(neighbors_v) > 1:
        local_lengths = []

        for nu in neighbors_u:
            if nu == v:
                continue
            if G.has_edge(u, nu):
                local_lengths.append(G[u][nu]['length'])

        for nv in neighbors_v:
            if nv == u:
                continue
            if G.has_edge(v, nv):
                local_lengths.append(G[v][nv]['length'])

        if local_lengths:
            avg = np.mean(local_lengths)
            if data["length"] < avg * MAX_CONNECTOR_BETWEEN_PARALLELS:
                return True

    return False


# ─────────────────────────────────────────────
# CLEAN GRAPH
# ─────────────────────────────────────────────
def clean_graph(G):

    to_remove = []

    for u, v, data in G.edges(data=True):

        if is_connector_edge(G, u, v, data):
            to_remove.append((u, v))

    G.remove_edges_from(to_remove)

    return G


# ─────────────────────────────────────────────
# REBUILD GEOMETRIES
# ─────────────────────────────────────────────
def graph_to_gdf(G, crs):

    geoms = []

    for u, v, data in G.edges(data=True):
        geoms.append(data["geometry"])

    return gpd.GeoDataFrame(geometry=geoms, crs=crs)


# ─────────────────────────────────────────────
# PIPELINE
# ─────────────────────────────────────────────
def clean_roads(input_file, output_file):

    print("Loading...")
    gdf = gpd.read_file(input_file)

    print("Reprojecting to EPSG:3857...")
    gdf = gdf.to_crs("EPSG:3857")

    lines = extract_lines(gdf)
    print(f"Lines: {len(lines)}")

    print("Building graph...")
    G = build_graph(lines)

    print(f"Nodes: {len(G.nodes)} | Edges: {len(G.edges)}")

    print("Cleaning topology...")
    G = clean_graph(G)

    print(f"After cleanup → Nodes: {len(G.nodes)} | Edges: {len(G.edges)}")

    print("Rebuilding geometry...")
    out = graph_to_gdf(G, gdf.crs)

    print("Exporting...")
    out = out.to_crs("EPSG:4326")
    out.to_file(output_file, driver="GeoJSON")

    print(f"Saved → {output_file}")

    return out


# ─────────────────────────────────────────────
if __name__ == "__main__":

    clean_roads(
        "autoroute.geojson",
        "autoroute_clean.geojson"
    )