from pathlib import Path

from qgis.core import QgsProject, QgsVectorLayer, Qgis

import config

from layers import save_layer_to_geopackage
from map_area import map_area_wgs84
from osm import (
    build_major_roads_query,
    extract_link_endpoint_node_ids,
    geometry_to_overpass_poly,
    overpass_ways_to_layer,
    query_connector_roads,
    run_overpass_query,
)


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


def run():
    project = QgsProject.instance()
    map_area = get_map_area(project)
    cfg = config.load_config()

    project_dir = Path(project.absolutePath())
    geopackage_path = project_dir / "BikeMS002.gpkg"
    geometry = map_area_wgs84(project, map_area)
    poly = geometry_to_overpass_poly(geometry)
    query = build_major_roads_query(poly)
    major_roads_result = run_overpass_query(query)
    endpoint_ids = extract_link_endpoint_node_ids(major_roads_result)
    connector_result = query_connector_roads(endpoint_ids)

    temp_major_roads = overpass_ways_to_layer(
        major_roads_result,
        "major_roads_preview",
        cfg["osm"]["fields"],
        "major",
    )
    temp_connectors = overpass_ways_to_layer(
        connector_result,
        "connectors_preview",
        cfg["osm"]["fields"],
        "connector"
    )

    major_roads = save_layer_to_geopackage(
        temp_major_roads,
        str(geopackage_path),
        "major_roads",
    )

    project.addMapLayer(major_roads)
    project.addMapLayer(temp_connectors)

    print("features:", major_roads.featureCount())
    print(f"Connector elements: " f"{len(connector_result.get('elements', []))}")
