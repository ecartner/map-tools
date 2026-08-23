from pathlib import Path
import tomllib

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "config.toml"


def load_config():
    with CONFIG_PATH.open("rb") as f:
        return tomllib.load(f)
