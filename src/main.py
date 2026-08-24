from pathlib import Path
from typing import Any

from qgis.core import QgsProject, QgsVectorLayer, Qgis

import config
import layers
import osm
from map_area import map_area_wgs84
from config import get_road_abbreviations

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
# Major roads acquisition
# --------------------------------------------------


def fetch_major_roads(project: QgsProject, cfg: dict) -> QgsVectorLayer:
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
        cfg["osm"]["fields"],
        "major",
    )
    connectors = osm.overpass_ways_to_layer(
        connector_result, "connectors_preview", cfg["osm"]["fields"], "connector"
    )
    layers.append_layer(major_roads, connectors)

    return major_roads


def rebuild_major_roads(project: QgsProject, cfg: dict) -> QgsVectorLayer:
    temp_major_roads = fetch_major_roads(project, cfg)

    major_roads = layers.save_to_geopackage(
        temp_major_roads, gpkg_path(), "major_roads"
    )

    layers.inspect_road_layer(major_roads)

    return major_roads


# --------------------------------------------------
# Major roads processing
# --------------------------------------------------


def process_major_roads(
    project: QgsProject,
    config: dict[str, Any],
    major_roads: QgsVectorLayer,
) -> None:
    layers.apply_named_style(major_roads, STYLE_DIR / "major_roads.qml")

    major_roads_with_labels = layers.create_major_road_label_layer(major_roads, config)
    temp_a_road_labels = layers.dissolve_major_road_label_layer(major_roads_with_labels)

    temp_b_road_labels = layers.prune_fields(
        temp_a_road_labels, KEEP_FIELDS, "major_road_labels"
    )

    abbreviations = get_road_abbreviations()
    layers.add_road_labels(temp_b_road_labels, abbreviations)

    major_road_labels = layers.save_to_geopackage(
        temp_b_road_labels, gpkg_path(), "major_road_labels"
    )
    layers.apply_named_style(major_road_labels, STYLE_DIR / "major_road_labels.qml")

    project.addMapLayer(major_road_labels)


def load_major_roads() -> QgsVectorLayer:
    return layers.load_from_geopackage(gpkg_path(), "major_roads")


# --------------------------------------------------
# Entry points
# --------------------------------------------------
def run() -> None:
    """
    Full rebuild from OSM.
    """

    project = QgsProject.instance()
    cfg = config.load_config()

    rebuild_major_roads(project, cfg)

    major_roads = load_major_roads()

    process_major_roads(project, cfg, major_roads)

    project.addMapLayer(major_roads)


def load_existing() -> None:
    """
    Development entry point.

    Skip Overpass and start with the existing GeoPackage.
    """

    project = QgsProject.instance()
    cfg = config.load_config()

    major_roads = load_major_roads()

    process_major_roads(project, cfg, major_roads)

    project.addMapLayer(major_roads)

