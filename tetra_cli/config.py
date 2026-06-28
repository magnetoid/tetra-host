"""Persistent CLI config: API base URL + session token.

Resolution order (highest first): environment variables, the config file,
then the built-in default. Env: ``TETRA_API_URL``, ``TETRA_TOKEN``,
``TETRA_CONFIG_DIR``.
"""

import json
import os
from pathlib import Path

DEFAULT_URL = "http://127.0.0.1:8088"


def config_dir() -> Path:
    return Path(os.environ.get("TETRA_CONFIG_DIR", str(Path.home() / ".config" / "tetra-host")))


def config_path() -> Path:
    return config_dir() / "config.json"


def load_config() -> dict[str, str]:
    data: dict[str, str] = {}
    path = config_path()
    if path.exists():
        try:
            loaded = json.loads(path.read_text())
            if isinstance(loaded, dict):
                data = loaded
        except (ValueError, OSError):
            data = {}
    url = os.environ.get("TETRA_API_URL") or data.get("url") or DEFAULT_URL
    token = os.environ.get("TETRA_TOKEN") or data.get("token") or ""
    return {"url": url.rstrip("/"), "token": token}


def save_config(url: str, token: str) -> Path:
    directory = config_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = config_path()
    path.write_text(json.dumps({"url": url.rstrip("/"), "token": token}, indent=2))
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return path
