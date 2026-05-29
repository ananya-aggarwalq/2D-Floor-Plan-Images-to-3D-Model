import os
os.environ["SHAPE_RESTORE_SHX"] = "YES"

import geopandas as gpd
import numpy as np
from shapely.geometry import LineString, Polygon, MultiPolygon
from shapely.ops import unary_union, linemerge, polygonize

# ==============================
# PARAMETERS
# ==============================
GRID_SIZE = 0.5
ROOM_MIN_AREA = 4.0
JUNK_THRESHOLD = 3.0

# ==============================
# STEP 1 — LOAD RAW VECTOR
# ==============================
print("\n🔹 Loading shapefile...")
gdf = gpd.read_file("raster_to_vector.shp")
print("Features loaded:", len(gdf))

# ==============================
# STEP 2 — EXTRACT WALL LINES
# ==============================
print("\n🔹 Extracting wall edges...")
lines = []

for geom in gdf.geometry:
    if geom is None:
        continue

    if geom.geom_type == "Polygon":
        lines.append(LineString(geom.exterior.coords))
        for interior in geom.interiors:
            lines.append(LineString(interior.coords))

    elif geom.geom_type == "MultiPolygon":
        for p in geom.geoms:
            lines.append(LineString(p.exterior.coords))

    elif geom.geom_type in ["LineString", "MultiLineString"]:
        lines.append(geom)

walls = gpd.GeoSeries(lines)
print("Wall segments:", len(walls))

# ==============================
# STEP 3 — MERGE WALL NETWORK
# ==============================
print("\n🔹 Merging walls...")
merged = linemerge(unary_union(walls))

if merged.geom_type == "LineString":
    merged_lines = [merged]
elif merged.geom_type == "MultiLineString":
    merged_lines = list(merged.geoms)
else:
    merged_lines = []

walls = gpd.GeoSeries(merged_lines)
print("Merged wall segments:", len(walls))

# ==============================
# STEP 4 — BUILD ROOMS
# ==============================
print("\n🔹 Detecting closed rooms...")
room_polys = list(polygonize(walls))
rooms = [p for p in room_polys if p.area > ROOM_MIN_AREA]
print("Rooms detected:", len(rooms))

# Remove isolated tiny junk
rooms = [r for r in rooms if r.area > JUNK_THRESHOLD]
print("Rooms after cleaning:", len(rooms))

# ==============================
# STEP 5 — GLOBAL TRANSFORM
# ==============================
print("\n🔹 Applying proper georeferencing (Helmert transform)...")

# Local coordinates (meters)
local_pts = np.array([
    [0,0],
    [282,0],
    [282,276],
    [0,276]
])

# # Global (lat, lon)
# global_pts = np.array([
#     [28.54371537858688, 77.1877568948139],
#     [28.54363114461907, 77.18794397888335],
#     [28.54347386842893, 77.18784674881141],
#     [28.543559280621263, 77.18765899418975]
    
# ])

global_pts = np.array([
    [28.543559280621263, 77.18765899418975], # was 4
    [28.54347386842893, 77.18784674881141],  # was 3
    [28.54363114461907, 77.18794397888335],  # was 2
    [28.54371537858688, 77.1877568948139]    # was 1
])

# Convert lat/lon to planar meters (approx)
lat0 = np.mean(global_pts[:,0])
lon0 = np.mean(global_pts[:,1])

R = 6378137
def latlon_to_xy(lat, lon):
    x = np.radians(lon - lon0) * R * np.cos(np.radians(lat0))
    y = np.radians(lat - lat0) * R
    return np.array([x,y])

global_xy = np.array([latlon_to_xy(lat,lon) for lat,lon in global_pts])

# Solve similarity transform
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

def transform_point(x,y):
    pt = np.array([x,y])
    res = scale * (Rm @ pt) + t

    lon = np.degrees(res[0] / (R * np.cos(np.radians(lat0)))) + lon0
    lat = np.degrees(res[1] / R) + lat0
    return (lon,lat)

print("\n🔹 Transforming room polygons to global coordinates...")

def transform_poly(poly):
    return Polygon([transform_point(x, y) for x, y in poly.exterior.coords])

rooms_global = [transform_poly(r) for r in rooms]

print("Transformed rooms:", len(rooms_global))


# ==============================
# STEP 6 — TRANSFORM ROOMS
# ==============================
print("\n🔹 Transforming room polygons to global coordinates...")

def transform_poly(poly):
    return Polygon([transform_point(x, y) for x, y in poly.exterior.coords])

rooms_global = [transform_poly(r) for r in rooms]

print("Transformed rooms:", len(rooms_global))

# ==============================
# STEP 7 — EXPORT GEOJSON
# ==============================
print("\n🔹 Exporting GeoJSON...")
rooms_gdf = gpd.GeoDataFrame(geometry=rooms_global, crs="EPSG:4326")
rooms_gdf.to_file("rooms_global.geojson", driver="GeoJSON")

print("✅ DONE — rooms_global.geojson created")



import geopandas as gpd
from shapely import affinity

print("🔹 Loading building...")
gdf = gpd.read_file("rooms_global.geojson")

# Convert to meters
utm = gdf.estimate_utm_crs()
gdf = gdf.to_crs(utm)

# -------------------------------
# PARAMETERS
# -------------------------------
ROTATE_DEG = -52      # rotation angle
SHIFT_X =  0 #-78          # meters East (+) / West (-)
SHIFT_Y =  0 #-4          # meters North (+) / South (-)

# -------------------------------
# 1️⃣ Rotation
# -------------------------------
center = gdf.unary_union.centroid
cx, cy = center.x, center.y

print(f"Rotating {ROTATE_DEG}° around center...")
gdf["geometry"] = gdf.geometry.apply(
    lambda geom: affinity.rotate(geom, ROTATE_DEG, origin=(cx, cy))
)

# -------------------------------
# 2️⃣ Translation
# -------------------------------
print(f"Shifting X={SHIFT_X}m, Y={SHIFT_Y}m...")
gdf["geometry"] = gdf.geometry.apply(
    lambda geom: affinity.translate(geom, xoff=SHIFT_X, yoff=SHIFT_Y)
)

# Back to lat/long
gdf = gdf.to_crs("EPSG:4326")

gdf.to_file("rooms_rotated_shifted.geojson", driver="GeoJSON")
print("✅ DONE — rotated and shifted")


#############################################################################
################ Collinear #################################################


import geopandas as gpd
import numpy as np
from shapely.geometry import LineString, Polygon

print("Loading GeoJSON...")
gdf = gpd.read_file("rooms_rotated_shifted.geojson")

utm = gdf.estimate_utm_crs()
gdf = gdf.to_crs(utm)

DIST_TOL = 0.005   # relaxed tolerance (meters)

# -----------------------------------------------------
# Check if 3 points are nearly collinear
# -----------------------------------------------------
def is_collinear(a, b, c, tol):
    ax, ay = a
    bx, by = b
    cx, cy = c

    # Area of triangle method
    area = abs((bx-ax)*(cy-ay) - (by-ay)*(cx-ax))
    base = np.hypot(cx-ax, cy-ay)
    if base == 0:
        return True
    height = area / base
    return height < tol

# -----------------------------------------------------
# Remove zig-zag vertices only (SAFE)
# -----------------------------------------------------
def remove_zigzag(coords):
    coords = list(coords)

    # Ensure ring closure preserved
    is_ring = coords[0] == coords[-1]
    if is_ring:
        coords = coords[:-1]

    if len(coords) <= 2:
        return coords

    new = [coords[0]]

    for i in range(1, len(coords)-1):
        if not is_collinear(coords[i-1], coords[i], coords[i+1], DIST_TOL):
            new.append(coords[i])

    new.append(coords[-1])

    # Reclose ring
    if is_ring:
        new.append(new[0])

    return new

# -----------------------------------------------------
print("🔹 Straightening walls without deleting shapes...")

clean_geoms = []

for geom in gdf.geometry:

    if geom.geom_type == "Polygon":
        ext = remove_zigzag(geom.exterior.coords)
        holes = [remove_zigzag(h.coords) for h in geom.interiors]
        clean_geoms.append(Polygon(ext, holes))

    elif geom.geom_type == "LineString":
        clean_geoms.append(LineString(remove_zigzag(geom.coords)))

    else:
        clean_geoms.append(geom)

gdf.geometry = clean_geoms

# Back to lat/lon
gdf = gdf.to_crs("EPSG:4326")
gdf.to_file("rooms_collinear.geojson", driver="GeoJSON")

print("✅ DONE — zigzag noise removed, ALL rooms preserved")
