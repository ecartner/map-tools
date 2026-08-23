from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsGeometry,
    QgsProject,
    QgsVectorLayer
)

def map_area_wgs84(
    project: QgsProject,
    layer: QgsVectorLayer,
) -> QgsGeometry:
    
    feature = next(layer.getFeatures())

    # Copy it so we don't modify the feature's actual geometry
    geometry = QgsGeometry(feature.geometry())

    wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
    transform = QgsCoordinateTransform(
        layer.crs(),
        wgs84,
        project.transformContext(),
    )

    geometry.transform(transform)

    return geometry