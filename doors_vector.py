import pandas as pd
import geopandas as gpd
from shapely.geometry import Point

# -----------------------------------
# Load CSV
# -----------------------------------
csv_file = "door_locations.csv"   # path to your CSV

df = pd.read_csv(csv_file)

# -----------------------------------
# Create Point Geometry
# -----------------------------------
geometry = [
    Point(xy) for xy in zip(df["center_x"], df["center_y"])
]

# -----------------------------------
# Convert to GeoDataFrame
# -----------------------------------
gdf = gpd.GeoDataFrame(
    df,
    geometry=geometry
)

# Optional: set coordinate reference system
# Since these are image pixel coordinates,
# you can leave CRS empty or use a custom CRS.
gdf.set_crs(epsg=3857, inplace=True, allow_override=True)

# -----------------------------------
# Save as Shapefile
# -----------------------------------
output_shp = "doors_vector.shp"

gdf.to_file(output_shp)

print(f"Shapefile saved as: {output_shp}")