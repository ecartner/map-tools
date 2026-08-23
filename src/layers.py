from collections import Counter

from qgis.core import (
    QgsCoordinateTransform,
    QgsProject,
    QgsVectorFileWriter,
    QgsVectorLayer,
)

def save_layer_to_geopackage(
    source_layer: QgsVectorLayer,
    geopackage_path: str,
    layer_name: str,
) -> QgsVectorLayer:
    project = QgsProject.instance()
    project_crs = project.crs()
    transform_context = project.transformContext()

    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = "GPKG"
    options.layerName = layer_name
    options.actionOnExistingFile = (
        QgsVectorFileWriter.CreateOrOverwriteLayer
    )

    if source_layer.crs() != project_crs:
        options.ct = QgsCoordinateTransform(
            source_layer.crs(),
            project_crs,
            transform_context,
        )

    result = QgsVectorFileWriter.writeAsVectorFormatV3(
        source_layer,
        geopackage_path,
        transform_context,
        options,
    )

    error_code = result[0]
    error_message = result[1]

    if error_code != QgsVectorFileWriter.NoError:
        raise RuntimeError(
            f"Failed to write {layer_name!r} to GeoPackage: "
            f"{error_message}"
        )

    layer = QgsVectorLayer(
        f"{geopackage_path}|layername={layer_name}",
        layer_name,
        "ogr",
    )

    if not layer.isValid():
        raise RuntimeError(
            f"GeoPackage layer {layer_name!r} was written but could not be loaded"
        )

    return layer

def append_layer(target_layer: QgsVectorLayer, source_layer: QgsVectorLayer):
    target_layer.dataProvider().addFeatures(
        feature for feature in source_layer.getFeatures()
    )
    target_layer.updateExtents()

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

    duplicate_ids = [
        osm_id
        for osm_id, count in Counter(osm_ids).items()
        if count > 1
    ]

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
            