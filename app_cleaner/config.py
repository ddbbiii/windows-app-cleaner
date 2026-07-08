from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any


APP_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = APP_DIR / "config.json"
DEFAULT_CONFIG: dict[str, Any] = {
    "hotkey": None,
    "allowlist_process_names": [],
    "autostart_enabled": False,
    "minimize_to_tray_on_launch": True,
    "cleanup_mode": "foreground_and_background",
}


def load_config() -> dict[str, Any]:
    config = deepcopy(DEFAULT_CONFIG)
    if CONFIG_PATH.exists():
        try:
            loaded = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            loaded = {}
        if isinstance(loaded, dict):
            config.update(loaded)

    allowlist = config.get("allowlist_process_names", [])
    if not isinstance(allowlist, list):
        allowlist = []
    config["allowlist_process_names"] = sorted(
        {str(item).strip() for item in allowlist if str(item).strip()},
        key=str.lower,
    )

    config["autostart_enabled"] = bool(config.get("autostart_enabled", False))
    config["minimize_to_tray_on_launch"] = bool(config.get("minimize_to_tray_on_launch", True))
    if config.get("cleanup_mode") not in {"foreground_only", "foreground_and_background"}:
        config["cleanup_mode"] = DEFAULT_CONFIG["cleanup_mode"]
    if not isinstance(config.get("hotkey"), dict):
        config["hotkey"] = None
    return config


def save_config(config: dict[str, Any]) -> None:
    merged = deepcopy(DEFAULT_CONFIG)
    merged.update(config)
    CONFIG_PATH.write_text(
        json.dumps(merged, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
