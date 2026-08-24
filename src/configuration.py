from pathlib import Path
from typing import Mapping
import tomllib

class SystemConfig:
    def __init__(self, path: Path) -> None:
        with path.open("rb") as file:
            self._config = tomllib.load(file)

    @property
    def major_road_labels(self) -> Mapping[str, list[str]]:
        return self._config["major_road_labels"]

    @property
    def osm_fields(self) -> Mapping[str, str]:
        return self._config["osm"]["fields"]

    @property
    def road_abbreviations(self) -> Mapping[str, str]:
        return self._config["road_abbreviations"]


    