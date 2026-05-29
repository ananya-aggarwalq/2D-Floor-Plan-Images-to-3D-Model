import os
os.environ["SHAPE_RESTORE_SHX"] = "YES"

import geopandas as gpd
import numpy as np

from shapely.geometry import Point
from shapely import affinity

# =========================================================
# PARAMETERS
# =========================================================

ROTATE_DEG = -52
SHIFT_X = 0
SHIFT_Y = 0

# IMPORTANT:
# image height of original floorplan image
# used to flip YOLO/OpenCV coordinates
IMAGE_HEIGHT = 276

# =========================================================
# STEP 1 — LOAD DOOR SHAPEFILE
# =========================================================

print("\n🔹 Loading door shapefile...")

doors_gdf = gpd.read_file("doors_vector.shp")

print("Doors loaded:", len(doors_gdf))

# =========================================================
# STEP 2 — CONTROL POINTS
# =========================================================

# Local image coordinates
local_pts = np.array([
    [0,0],
    [282,0],
    [282,276],
    [0,276]
])

# Real-world GPS coordinates
global_pts = np.array([
    [28.543559280621263, 77.18765899418975],
    [28.54347386842893, 77.18784674881141],
    [28.54363114461907, 77.18794397888335],
    [28.54371537858688, 77.1877568948139]
])

# =========================================================
# STEP 3 — LAT/LON → LOCAL METERS
# =========================================================

lat0 = np.mean(global_pts[:,0])
lon0 = np.mean(global_pts[:,1])

R = 6378137

def latlon_to_xy(lat, lon):

    x = np.radians(lon - lon0) * R * np.cos(np.radians(lat0))

    y = np.radians(lat - lat0) * R

    return np.array([x, y])

global_xy = np.array([
    latlon_to_xy(lat, lon)
    for lat, lon in global_pts
])

# =========================================================
# STEP 4 — SOLVE HELMERT TRANSFORM
# =========================================================

def solve_similarity(A, B):

    A_mean = A.mean(axis=0)
    B_mean = B.mean(axis=0)

    A_c = A - A_mean
    B_c = B - B_mean

    U, S, Vt = np.linalg.svd(A_c.T @ B_c)

    Rm = U @ Vt

    scale = S.sum() / (A_c**2).sum()

    t = B_mean - scale * (Rm @ A_mean)

    return scale, Rm, t

scale, Rm, t = solve_similarity(local_pts, global_xy)

# =========================================================
# STEP 5 — TRANSFORM LOCAL → GPS
# =========================================================

def transform_point(x, y):

    pt = np.array([x, y])

    res = scale * (Rm @ pt) + t

    lon = np.degrees(
        res[0] / (R * np.cos(np.radians(lat0)))
    ) + lon0

    lat = np.degrees(res[1] / R) + lat0

    return (lon, lat)

# =========================================================
# STEP 6 — TRANSFORM DOOR POINTS
# =========================================================

print("\n🔹 Transforming door points...")

global_points = []

for geom in doors_gdf.geometry:

    if geom is None:
        continue

    # -----------------------------------------
    # IMPORTANT FIX:
    # Flip Y-axis from image coordinates
    # -----------------------------------------

    x = geom.x

    y = IMAGE_HEIGHT - geom.y

    lon, lat = transform_point(x, y)

    global_points.append(Point(lon, lat))

# =========================================================
# STEP 7 — CREATE GEO DATAFRAME
# =========================================================

doors_global = gpd.GeoDataFrame(
    doors_gdf.drop(columns="geometry"),
    geometry=global_points,
    crs="EPSG:4326"
)

print("Global doors:", len(doors_global))

# =========================================================
# STEP 8 — LOAD ROOM GEOJSON
# =========================================================

print("\n🔹 Loading room geometry...")

rooms_gdf = gpd.read_file("rooms_collinear.geojson")

# Convert BOTH to same projected CRS
utm = rooms_gdf.estimate_utm_crs()

rooms_gdf = rooms_gdf.to_crs(utm)

doors_global = doors_global.to_crs(utm)

# =========================================================
# STEP 9 — USE SAME ROTATION CENTER
# =========================================================

print("\n🔹 Computing room centroid...")

room_center = rooms_gdf.unary_union.centroid

cx = room_center.x
cy = room_center.y

print(f"Room centroid: ({cx}, {cy})")

# =========================================================
# STEP 10 — APPLY SAME ROTATION
# =========================================================

print("\n🔹 Applying rotation...")

doors_global["geometry"] = doors_global.geometry.apply(
    lambda geom: affinity.rotate(
        geom,
        ROTATE_DEG,
        origin=(cx, cy)
    )
)

# =========================================================
# STEP 11 — APPLY SAME SHIFT
# =========================================================

print("\n🔹 Applying translation...")

doors_global["geometry"] = doors_global.geometry.apply(
    lambda geom: affinity.translate(
        geom,
        xoff=SHIFT_X,
        yoff=SHIFT_Y
    )
)

# =========================================================
# STEP 12 — CONVERT BACK TO LAT/LON
# =========================================================

doors_global = doors_global.to_crs("EPSG:4326")

# =========================================================
# STEP 13 — EXPORT FINAL GEOJSON
# =========================================================

print("\n🔹 Exporting GeoJSON...")

doors_global.to_file(
    "doors_aligned.geojson",
    driver="GeoJSON"
)

print("\n✅ DONE — doors_aligned.geojson created")
print("✅ Doors should now perfectly align with rooms")