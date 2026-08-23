import json
import urllib.parse
import urllib.request

from qgis.core import (
    QgsFeature,
    QgsField,
    QgsGeometry,
    QgsPointXY,
    QgsProject,
    QgsVectorLayer,
)

from PyQt5.QtCore import QVariant

MAJOR_HIGHWAYS = [
    "motorway",
    "motorway_link",
    "trunk",
    "trunk_link",
    "primary",
    "primary_link",
    "secondary",
    "secondary_link",
]

LINK_HIGHWAYS = [
    "motorway_link",
    "trunk_link",
    "primary_link",
    "secondary_link",
]

CONNECTOR_HIGHWAYS = [
    "tertiary",
    "tertiary_link",
    "unclassified",
    "residential",
]

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

def geometry_to_overpass_poly(geometry: QgsGeometry) -> str:
    polygon = geometry.asPolygon()

    if not polygon:
        raise RuntimeError("map_area is not a simply polygon")

    exterior_ring = polygon[0]
    
    coords = " ".join(
        f"{point.y():.7f} {point.x():.7f}"
        for point in exterior_ring
    )

    return f'poly:"{coords}"'


def build_major_roads_query(poly: str) -> str:
    highway_regex = "|".join(MAJOR_HIGHWAYS)

    return f"""
[out:json][timeout:120];

way
  ["highway"~"^({highway_regex})$"]
  ({poly});

out body geom;
""".strip()

def run_overpass_query(query: str) -> dict:
    data = urllib.parse.urlencode({"data": query}).encode("utf-8")

    request = urllib.request.Request(
        OVERPASS_URL,
        data=data,
        headers={
            "User-Agent": "qgis-map-tools/0.1",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        print("OVERPASS QUERY:")
        print(query)
        print()
        print("OVERPASS ERROR:")
        print(error.read().decode("utf-8"))
        raise


def overpass_ways_to_layer(
    result: dict,
    layer_name: str,
    osm_fields: dict,
    road_role: str,
    ) -> QgsVectorLayer:
    layer = QgsVectorLayer(
        "LineString?crs=EPSG:4326",
        layer_name,
        "memory",
    )

    provider = layer.dataProvider()
    provider.addAttributes([
        QgsField("osm_id", QVariant.LongLong),
        QgsField("road_role", QVariant.String),
    ])

    provider.addAttributes([
      QgsField(field_name, QVariant.String)  
      for field_name in osm_fields.values()
    ])

    layer.updateFields()

    features = []
    for element in result.get("elements", []):
        if element.get("type") != "way":
            continue

        geometry = element.get("geometry")
        if not geometry:
            continue
    
        points = [
            QgsPointXY(node["lon"], node["lat"])
            for node in geometry
        ]

        if len(points) < 2:
            continue

        tags = element.get("tags", {})

        feature = QgsFeature(layer.fields())
        feature.setGeometry(QgsGeometry.fromPolylineXY(points))
        feature["osm_id"] = element["id"]
        feature["road_role"] = road_role

        for tag_name, field_name in osm_fields.items():
            feature[field_name] = tags.get(tag_name)

        features.append(feature)

    provider.addFeatures(features)
    layer.updateExtents()

    return layer

def extract_link_endpoint_node_ids(result: dict) -> set[int]:
    node_ids: set[int] = set()

    for element in result.get("elements", []):
        if element.get("type") != "way":
            continue

        tags = element.get("tags", {})
        highway = tags.get("highway")

        if highway not in LINK_HIGHWAYS:
            continue

        nodes = element.get("nodes", [])
        if not nodes:
            continue

        node_ids.add(nodes[0])
        node_ids.add(nodes[-1])

    return node_ids
        
def fetch_connector_roads(node_ids: set[int]) -> dict:
    if not node_ids:
        return {"elements": []}

    node_query = ",".join(str(node_id) for node_id in sorted(node_ids))
    highway_regex = "|".join(sorted(CONNECTOR_HIGHWAYS))

    query = f"""
[out:json][timeout:120];

node(id:{node_query})->.endpoints;

way(bn.endpoints)
  ["highway"~"^({highway_regex})$"];

out geom;
""".strip()

    return run_overpass_query(query)
        
    