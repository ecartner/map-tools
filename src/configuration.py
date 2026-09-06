from collections.abc import Mapping, Sequence
from pathlib import Path

from qgis.core import QgsProject

import tomllib


class SystemConfig:
    def __init__(self, path: Path) -> None:
        with path.open("rb") as file:
            self._config = tomllib.load(file)

    @property
    def major_road_labels(self) -> Mapping[str, Sequence[str]]:
        return self._config["major_road_labels"]

    @property
    def minor_road_labels(self) -> Mapping[str, Sequence[str]]:
        return self._config["minor_road_labels"]

    @property
    def osm_fields(self) -> Mapping[str, str]:
        return self._config["osm"]["fields"]

    @property
    def road_abbreviations(self) -> Mapping[str, str]:
        return self._config["road_abbreviations"]

    @property
    def detail_green_areas(self) -> Mapping[str, Sequence[str]]:
        return self._config["detail"]["green_areas"]

    @property
    def project_dir(self) -> Path:
        filename = QgsProject.instance().fileName()

        if not filename:
            raise RuntimeError("QGIS project must be saved first")

        return Path(filename).resolve().parent

    @property
    def gpkg_path(self) -> Path:
        return self.project_dir / "data" / "map.gpkg"

    @property
    def style_dir(self) -> Path:
        return self.project_dir / "styles"
