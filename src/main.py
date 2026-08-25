from pathlib import Path
from typing import Any

from qgis.core import QgsProject, QgsVectorLayer, Qgis

import labels
import layers
import osm
from map_area import map_area_wgs84
from configuration import SystemConfig

# --------------------
# Paths
# --------------------

TOOL_ROOT = Path(__file__).resolve().parent.parent

CONFIG_PATH = TOOL_ROOT / "config" / "config.toml"
STYLE_DIR = TOOL_ROOT / "styles"

KEEP_FIELDS = ["road_name", "geometry"]


def project_dir() -> Path:
    filename = QgsProject.instance().fileName()

    if not filename:
        raise RuntimeError("QGIS project must be saved first")

    return Path(filename).resolve().parent


def gpkg_path() -> Path:
    return project_dir() / "data" / "map.gpkg"


# --------------------------------------------------
# Project Inputs
# --------------------------------------------------


def get_map_area(project: QgsProject) -> QgsVectorLayer:
    layers = project.mapLayersByName("map_area")

    if not layers:
        raise RuntimeError("Layer 'map_area' was not found")

    if len(layers) > 1:
        raise RuntimeError("More than one layer named 'map_area' exists")

    layer = layers[0]

    if not isinstance(layer, QgsVectorLayer):
        raise RuntimeError("'map_area' is not a vector layer")

    if not layer.isValid():
        raise RuntimeError("'map_area' is not a valid layer")

    if layer.geometryType() != Qgis.GeometryType.Polygon:
        raise RuntimeError("'map_area' must be a polygon layer")

    if layer.featureCount() != 1:
        raise RuntimeError(
            f"'map_area' must contain exactly one feature; found {layer.featureCount()}"
        )

    return layer


# --------------------------------------------------
# Roads acquisition
# --------------------------------------------------


def fetch_major_roads(project: QgsProject, config: SystemConfig) -> QgsVectorLayer:
    map_area = get_map_area(project)
    geometry = map_area_wgs84(project, map_area)
    poly = osm.geometry_to_overpass_poly(geometry)
    query = osm.build_major_roads_query(poly)
    major_roads_result = osm.run_overpass_query(query)
    endpoint_ids = osm.extract_link_endpoint_node_ids(major_roads_result)
    connector_result = osm.fetch_connector_roads(endpoint_ids)
    major_roads = osm.overpass_ways_to_layer(
        major_roads_result,
        "major_roads_preview",
        config.osm_fields,
        "major",
    )
    connectors = osm.overpass_ways_to_layer(
        connector_result, "connectors_preview", config.osm_fields, "connector"
    )
    layers.append_layer(major_roads, connectors)

    return major_roads

def fetch_minor_roads(project: QgsProject, config: SystemConfig) -> QgsVectorLayer:
    map_area = get_map_area(project)
    geometry = map_area_wgs84(project, map_area)
    poly = osm.geometry_to_overpass_poly(geometry)
    query = osm.build_minor_roads_query(poly)
    result = osm.run_overpass_query(query)
    minor_roads = osm.overpass_ways_to_layer(
        result,
        "minor_roads_preview",
        config.osm_fields,
        "minor",
    )
    return minor_roads
    

def rebuild_major_roads(project: QgsProject, config: SystemConfig) -> QgsVectorLayer:
    temp_major_roads = fetch_major_roads(project, config)

    major_roads = layers.save_to_geopackage(
        temp_major_roads, gpkg_path(), "major_roads"
    )

    layers.inspect_road_layer(major_roads)

    return major_roads

def rebuild_minor_roads(project: QgsProject, config: SystemConfig) -> QgsVectorLayer:
    temp_minor_roads = fetch_minor_roads(project, config)

    minor_roads = layers.save_to_geopackage(
        temp_minor_roads, gpkg_path(), "minor_roads"
    )

    layers.inspect_road_layer(minor_roads)

    return minor_roads


# --------------------------------------------------
# Roads processing
# --------------------------------------------------


def process_major_roads(
    project: QgsProject,
    config: SystemConfig,
    major_roads: QgsVectorLayer,
) -> None:
    layers.apply_named_style(major_roads, STYLE_DIR / "major_roads.qml")

    major_roads_with_labels = labels.create_road_name_layer(major_roads, config.major_road_labels)
    temp_a_road_labels = labels.dissolve_road_name_layer(major_roads_with_labels)

    temp_b_road_labels = layers.prune_fields(
        temp_a_road_labels, KEEP_FIELDS, "major_road_labels"
    )

    abbreviations = config.road_abbreviations
    labels.add_road_labels(temp_b_road_labels, abbreviations)

    major_road_labels = layers.save_to_geopackage(
        temp_b_road_labels, gpkg_path(), "major_road_labels"
    )

    layers.apply_named_style(major_road_labels, STYLE_DIR / "major_road_labels.qml")

    project.addMapLayer(major_road_labels)

def process_minor_roads(
    project: QgsProject,
    config: SystemConfig,
    minor_roads: QgsVectorLayer,
) -> None:
    
    named_minor_roads = labels.create_road_name_layer(minor_roads, config.minor_road_labels)
    temp_a = labels.dissolve_road_name_layer(named_minor_roads)
    temp_b = layers.prune_fields(temp_a, KEEP_FIELDS, "minor_road_labels")
    abbreviations = config.road_abbreviations
    labels.add_road_labels(temp_b, abbreviations)
    minor_road_labels = layers.save_to_geopackage(
        temp_b, gpkg_path(), "minor_road_labels"
    )
    project.addMapLayer(minor_road_labels)


def load_major_roads() -> QgsVectorLayer:
    return layers.load_from_geopackage(gpkg_path(), "major_roads")

def load_minor_roads() -> QgsVectorLayer:
    return layers.load_from_geopackage(gpkg_path(), "minor_roads")


# --------------------------------------------------
# Entry points
# --------------------------------------------------
def run() -> None:
    """
    Full rebuild from OSM.
    """

    project = QgsProject.instance()
    config = SystemConfig(CONFIG_PATH)


    rebuild_major_roads(project, config)

    major_roads = load_major_roads()

    process_major_roads(project, config, major_roads)

    project.addMapLayer(major_roads)


def run_minor() -> None:
    """
    Full rebuild of minor roads from OSM
    """

    project = QgsProject.instance()
    config = SystemConfig(CONFIG_PATH)
    rebuild_minor_roads(project, config)
    minor_roads = load_minor_roads()
    process_minor_roads(project, config, minor_roads)
    project.addMapLayer(minor_roads)


    
def load_existing() -> None:
    """
    Development entry point.

    Skip Overpass and start with the existing GeoPackage.
    """

    project = QgsProject.instance()
    config = SystemConfig(CONFIG_PATH)

    major_roads = load_major_roads()

    process_major_roads(project, config, major_roads)

    project.addMapLayer(major_roads)

    minor_roads = load_minor_roads()
    process_minor_roads(project, config, minor_roads)
    project.addMapLayer(minor_roads)

