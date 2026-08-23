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