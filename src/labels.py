from collections.abc import Mapping, Sequence
from typing import Any

from qgis.core import (
    NULL,
    QgsFeature,
    QgsField,
    QgsProcessing,
    QgsVectorLayer
)

from qgis.PyQt.QtCore import QVariant
from qgis import processing

from text import replace_words


def add_road_labels(
    layer: QgsVectorLayer,
    abbreviations: Mapping[str, str],
) -> None:
    provider = layer.dataProvider()
    provider.addAttributes([
        QgsField("road_label", QVariant.String),
    ])
    layer.updateFields()

    road_name_idx = layer.fields().indexOf("road_name")
    road_label_idx = layer.fields().indexOf("road_label")

    changes: dict[int, dict[int, str]] = {}

    for feature in layer.getFeatures():
        road_name = feature[road_name_idx]

        if road_name == NULL:
            continue

        if road_name is None:
            continue

        changes[feature.id()] = {
            road_label_idx: replace_words(str(road_name), abbreviations),
        }

    provider.changeAttributeValues(changes)


def pick_highway_segment_label(feature: QgsFeature, config: dict[str, Any]) -> str | None:
    highway = feature["highway"]
    name = feature["name"]
    ref = feature["ref"]

    if highway in config["ref_first"]:
        return ref or name

    if highway in config["name_first"]:
        return name or ref

    return name or ref

def create_major_road_label_layer(major_roads, label_config: Mapping[str, Sequence[str]]):
    result = processing.run(
        "native:savefeatures",
        {
            "INPUT": major_roads,
            "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
        },
    )

    layer = QgsVectorLayer(result["OUTPUT"], "major_roads_labels_work", "ogr")

    provider = layer.dataProvider()

    provider.addAttributes(
        [
            QgsField("road_name", QVariant.String),
        ]
    )
    layer.updateFields()

    label_index = layer.fields().indexFromName("road_name")

    changes = {}

    for feature in layer.getFeatures():
        label = pick_highway_segment_label(feature, label_config)

        if label is not None:
            changes[feature.id()] = {
                label_index: label,
            }

    provider.changeAttributeValues(changes)

    return layer


def dissolve_major_road_label_layer(labeled_roads: QgsVectorLayer) -> QgsVectorLayer:
    result = processing.run(
        "native:dissolve",
        {
            "INPUT": labeled_roads,
            "FIELD": ["road_name"],
            "SEPARATE_DISJOINT": True,
            "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
        },
    )

    return result["OUTPUT"]
