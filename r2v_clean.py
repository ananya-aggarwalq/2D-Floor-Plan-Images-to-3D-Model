# =========================================================
# RASTER → VECTOR (ROBUST PyQGIS SCRIPT FOR macOS)
# =========================================================

import os
import time
import processing
import numpy as np
from osgeo import gdal

from qgis.core import (
    QgsProject,
    QgsRasterLayer,
    QgsVectorLayer
)

# =========================================================
# PATHS
# =========================================================

BASE_DIR = "/Users/ananyaaggarwal/Documents/Ananya/iwayplus/qgis"

INPUT_RASTER = f"{BASE_DIR}/floor_plan.png"
ERODED_RASTER = f"{BASE_DIR}/eroded.tif"

INTERMEDIATE_GPKG = f"{BASE_DIR}/intermediate_polygon.gpkg"
FINAL_GPKG = f"{BASE_DIR}/final_vector.gpkg"

POLY_SHP = f"{BASE_DIR}/intermediate_polygon.shp"
FINAL_SHP = f"{BASE_DIR}/raster_to_vector.shp"

THRESHOLD_VALUE = 255
SIEVE_SIZE = 500


# =========================================================
# UTIL FUNCTIONS
# =========================================================

def delete_if_exists(path):
    extensions = [".shp", ".shx", ".dbf", ".prj", ".cpg"]
    base = path.replace(".shp", "")
    
    for ext in extensions:
        file = base + ext
        if os.path.exists(file):
            os.remove(file)


def remove_layer_by_name(name):
    layers = QgsProject.instance().mapLayersByName(name)
    for layer in layers:
        QgsProject.instance().removeMapLayer(layer.id())


def clean_start():
    remove_layer_by_name("raster_to_vector")
    remove_layer_by_name("final_vector")
    remove_layer_by_name("polygons")

    delete_if_exists(POLY_SHP)
    delete_if_exists(FINAL_SHP)


# =========================================================
# STEP 1: LOAD RASTER
# =========================================================

def load_raster():
    raster = QgsRasterLayer(INPUT_RASTER, "input_raster")
    if not raster.isValid():
        raise Exception("❌ Input raster could not be loaded")

    QgsProject.instance().addMapLayer(raster)
    print("✅ Input raster loaded")

    return raster


# =========================================================
# STEP 2: THRESHOLD
# =========================================================

def threshold_raster(raster):
    binary = processing.run(
        "qgis:rastercalculator",
        {
            "EXPRESSION": f'"input_raster@1" < {THRESHOLD_VALUE}',
            "LAYERS": [raster],
            "OUTPUT": "TEMPORARY_OUTPUT"
        }
    )["OUTPUT"]

    print("✅ Thresholding done")
    return binary


# =========================================================
# STEP 3: SIEVE
# =========================================================

def sieve_raster(binary):
    cleaned = processing.run(
        "gdal:sieve",
        {
            "INPUT": binary,
            "THRESHOLD": SIEVE_SIZE,
            "CONNECTEDNESS": 8,
            "OUTPUT": "TEMPORARY_OUTPUT"
        }
    )["OUTPUT"]

    print("✅ Noise removed")
    return cleaned


# =========================================================
# STEP 4: WRITE RASTER TO DISK
# =========================================================

def write_raster_to_disk(cleaned):
    processing.run(
        "gdal:translate",
        {
            "INPUT": cleaned,
            "OUTPUT": ERODED_RASTER
        }
    )

    time.sleep(0.5)

    if not os.path.exists(ERODED_RASTER):
        raise Exception("❌ Eroded raster was not written to disk")

    eroded_layer = QgsRasterLayer(ERODED_RASTER, "eroded_disk")

    if not eroded_layer.isValid():
        raise Exception("❌ Eroded raster exists but QGIS cannot load it")

    QgsProject.instance().addMapLayer(eroded_layer)

    print("✅ Eroded raster loaded from disk")

    # debug values
    ds = gdal.Open(ERODED_RASTER)
    arr = ds.GetRasterBand(1).ReadAsArray()

    print("Unique raster values:", np.unique(arr))
    print("Foreground pixel count:", np.sum(arr == 1))

    return eroded_layer


# =========================================================
# STEP 5: CLEAN INTERMEDIATE FILE
# =========================================================

def clean_intermediate():
    if os.path.exists(INTERMEDIATE_GPKG):
        os.remove(INTERMEDIATE_GPKG)
        print("🗑️ Old intermediate GeoPackage removed")


# =========================================================
# STEP 6: POLYGONIZE
# =========================================================

def polygonize():
    eroded_layer = QgsProject.instance().mapLayersByName("eroded_disk")[0]

    print("Using raster layer:", eroded_layer.name())
    print("Layer ID:", eroded_layer.id())

    processing.run(
        "gdal:polygonize",
        {
            "INPUT": ERODED_RASTER,
            "BAND": 1,
            "FIELD": "value",
            "OUTPUT": POLY_SHP
        }
    )

    print("✅ GDAL polygonize finished")


# =========================================================
# STEP 7: LOAD & VERIFY POLYGONS
# =========================================================

def load_polygons():
    poly_layer = QgsVectorLayer(POLY_SHP, "polygons", "ogr")

    print("Polygon layer valid:", poly_layer.isValid())
    print("Polygon feature count:", poly_layer.featureCount())

    QgsProject.instance().addMapLayer(poly_layer)

    return poly_layer


# =========================================================
# STEP 8: FIX GEOMETRIES
# =========================================================

def fix_geometries():
    processing.run(
        "qgis:fixgeometries",
        {
            "INPUT": POLY_SHP,
            "OUTPUT": FINAL_SHP
        }
    )

    print("✅ Geometry fixing completed")


# =========================================================
# STEP 9: LOAD FINAL LAYER
# =========================================================

def load_final_layer():
    final_layer = QgsVectorLayer(FINAL_SHP, "Final Vector", "ogr")
    QgsProject.instance().addMapLayer(final_layer)

    print("🎉 Raster → Vector pipeline FULLY completed")


# =========================================================
# MAIN PIPELINE
# =========================================================

def run_pipeline():
    clean_start()
    raster = load_raster()
    binary = threshold_raster(raster)
    cleaned = sieve_raster(binary)
    write_raster_to_disk(cleaned)
    clean_intermediate()
    polygonize()
    load_polygons()
    fix_geometries()
    load_final_layer()


# =========================================================
# EXECUTE
# =========================================================

run_pipeline()