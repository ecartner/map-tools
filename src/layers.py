from typing import Any

from collections import Counter
from collections.abc import Collection

from pathlib import Path

from qgis.core import (
    QgsCoordinateTransform,
    QgsFeature,
    QgsField,
    QgsProcessing,
    QgsProcessingContext,
    QgsProcessingFeedback,
    QgsProject,
    QgsVectorFileWriter,
    QgsVectorLayer,
)

from qgis.PyQt.QtCore import QVariant
from qgis import processing


def append_layer(target_layer: QgsVectorLayer, source_layer: QgsVectorLayer):
    target_layer.dataProvider().addFeatures(
        feature for feature in source_layer.getFeatures()
    )
    target_layer.updateExtents()


def apply_named_style(
    layer: QgsVectorLayer,
    style_path: Path,
) -> None:
    error_message, success = layer.loadNamedStyle(str(style_path))

    if not success:
        raise RuntimeError(f"Unable to load style '{style_path}': " f"{error_message}")

    layer.triggerRepaint()


def inspect_road_layer(layer: QgsVectorLayer) -> None:
    print(f"Layer: {layer.name()}")
    print(f"Features: {layer.featureCount()}")
    print()

    field_names = [field.name() for field in layer.fields()]
    print("Fields:")
    for name in field_names:
        print(f"   {name}")
    print()

    highway_counts = Counter()
    role_counts = Counter()

    missing_geometry = 0
    missing_osm_id = 0
    osm_ids = []

    for feature in layer.getFeatures():
        if not feature.hasGeometry() or feature.geometry().isEmpty():
            missing_geometry += 1
        if "highway" in field_names:
            highway_counts[str(feature["highway"])] += 1

        if "road_role" in field_names:
            role_counts[str(feature["road_role"])] += 1

        if "osm_id" in field_names:
            osm_id = feature["osm_id"]

            if osm_id is None:
                missing_osm_id += 1
            else:
                osm_ids.append(osm_id)

    duplicate_ids = [osm_id for osm_id, count in Counter(osm_ids).items() if count > 1]

    print("Highway classes:")
    for highway, count in highway_counts.most_common():
        print(f"  {highway:20} {count}")
    print()

    print("Road roles:")
    for role, count in role_counts.most_common():
        print(f"  {role:20} {count}")
    print()

    print(f"Missing geometry: {missing_geometry}")
    print(f"Missing OSM IDs:  {missing_osm_id}")
    print(f"Duplicate OSM IDs: {len(duplicate_ids)}")

    if duplicate_ids:
        print("First duplicate IDs:")
        for osm_id in duplicate_ids[:20]:
            print(f"  {osm_id}")


def load_from_geopackage(gpkg_path: Path, layer_name: str) -> QgsVectorLayer:
    uri = f"{str(gpkg_path)}|layername={layer_name}"
    layer = QgsVectorLayer(uri, layer_name, "ogr")

    if not layer.isValid():
        raise RuntimeError(f"Failed to load {layer_name} from {gpkg_path}")

    return layer


def road_label(feature: QgsFeature, config: dict[str, Any]) -> str | None:
    highway = feature["highway"]
    name = feature["name"]
    ref = feature["ref"]

    label_config = config["major_road_labels"]

    if highway in label_config["ref_first"]:
        return ref or name

    if highway in label_config["name_first"]:
        return name or ref

    return name or ref


def create_major_road_label_layer(major_roads, config):
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
            QgsField("road_label", QVariant.String),
        ]
    )
    layer.updateFields()

    label_index = layer.fields().indexFromName("road_label")

    changes = {}

    for feature in layer.getFeatures():
        label = road_label(feature, config)

        if label is not None:
            changes[feature.id()] = {
                label_index: label,
            }

    provider.changeAttributeValues(changes)

    return layer


def dissolve_major_road_labels(labeled_roads: QgsVectorLayer) -> QgsVectorLayer:
    result = processing.run(
        "native:dissolve",
        {
            "INPUT": labeled_roads,
            "FIELD": ["road_label"],
            "SEPARATE_DISJOINT": True,
            "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
        },
    )

    return result["OUTPUT"]


def prune_fields(
    layer: QgsVectorLayer, keep: Collection[str], name: str
) -> QgsVectorLayer:
    drop: list[str] = [
        field.name() for field in layer.fields() if field.name() not in keep
    ]

    if not drop:
        return layer

    result: dict[str, object] = processing.run(
        "native:deletecolumn",
        {
            "INPUT": layer,
            "COLUMN": drop,
            "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
        },
    )

    output = result["OUTPUT"]

    if isinstance(output, QgsVectorLayer):
        output.setName(name)
        return output

    return QgsVectorLayer(
        str(output),
        name,
        "ogr",
    )


def save_to_geopackage(
    source_layer: QgsVectorLayer,
    gpkg_path: Path,
    layer_name: str,
) -> QgsVectorLayer:
    project = QgsProject.instance()
    project_crs = project.crs()
    transform_context = project.transformContext()

    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = "GPKG"
    options.layerName = layer_name
    options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer

    if source_layer.crs() != project_crs:
        options.ct = QgsCoordinateTransform(
            source_layer.crs(),
            project_crs,
            transform_context,
        )

    result = QgsVectorFileWriter.writeAsVectorFormatV3(
        source_layer,
        str(gpkg_path),
        transform_context,
        options,
    )

    error_code = result[0]
    error_message = result[1]

    if error_code != QgsVectorFileWriter.NoError:
        raise RuntimeError(
            f"Failed to write {layer_name!r} to GeoPackage: " f"{error_message}"
        )

    layer = QgsVectorLayer(
        f"{gpkg_path}|layername={layer_name}",
        layer_name,
        "ogr",
    )

    if not layer.isValid():
        raise RuntimeError(
            f"GeoPackage layer {layer_name!r} was written but could not be loaded"
        )

    return layer
