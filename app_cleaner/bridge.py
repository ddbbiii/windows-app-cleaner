from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

from .config import load_config, save_config
from .desktop_apps import (
    AppCandidate,
    WindowCandidate,
    close_non_allowlisted_windows,
    close_selected_windows,
    enumerate_desktop_windows,
    group_apps,
)


SELF_PROCESS_NAMES = {
    "electron.exe",
    "node.exe",
    "python.exe",
    "pythonw.exe",
}


def _json(data: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    sys.stdout.flush()


def _safe_error(exc: Exception) -> None:
    _json({"ok": False, "error": str(exc)})


def _filtered_windows() -> list[WindowCandidate]:
    windows = enumerate_desktop_windows(os.getpid())
    return [
        item
        for item in windows
        if item.process_name.lower() not in SELF_PROCESS_NAMES
    ]


def _app_sort_key(item: AppCandidate) -> tuple[int, str]:
    if item.foreground_window_count:
        group = 0
    else:
        group = 1
    return (group, item.process_name.lower())


def _serialize_app_row(item: AppCandidate, allowlist: set[str], scope: str) -> dict[str, Any]:
    is_foreground = scope == "foreground"
    foreground_count = item.foreground_window_count if is_foreground else 0
    background_count = item.background_window_count if not is_foreground else 0
    window_count = foreground_count + background_count
    state = "前台" if is_foreground else "后台"
    return {
        "rowKey": f"{item.process_name.lower()}:{scope}",
        "scope": scope,
        "processName": item.process_name,
        "displayTitle": item.display_title,
        "exePath": item.exe_path,
        "state": state,
        "isForeground": is_foreground,
        "isBackground": not is_foreground,
        "foregroundWindowCount": foreground_count,
        "backgroundWindowCount": background_count,
        "windowCount": window_count,
        "allowed": item.process_name.lower() in allowlist,
    }


def _serialize_app_rows(item: AppCandidate, allowlist: set[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if item.foreground_window_count:
        rows.append(_serialize_app_row(item, allowlist, "foreground"))
    if item.background_window_count:
        rows.append(_serialize_app_row(item, allowlist, "background"))
    return rows


def _state_payload(message: str | None = None, result: Any | None = None) -> dict[str, Any]:
    config = load_config()
    allowlist = {name.lower() for name in config["allowlist_process_names"]}
    windows = _filtered_windows()
    apps = sorted(group_apps(windows), key=_app_sort_key)
    serialized = [
        row
        for item in apps
        for row in _serialize_app_rows(item, allowlist)
    ]
    foreground = sum(1 for item in serialized if item["isForeground"])
    background = sum(1 for item in serialized if item["isBackground"])
    cleanable = sum(1 for item in serialized if not item["allowed"])

    payload: dict[str, Any] = {
        "ok": True,
        "message": message or "",
        "config": {
            "cleanupMode": config["cleanup_mode"],
            "allowlistProcessNames": config["allowlist_process_names"],
            "autostartEnabled": config["autostart_enabled"],
            "minimizeToTrayOnLaunch": config["minimize_to_tray_on_launch"],
            "hotkey": config["hotkey"],
        },
        "counts": {
            "foreground": foreground,
            "background": background,
            "cleanable": cleanable,
            "allowlist": len(allowlist),
            "apps": len(serialized),
        },
        "apps": serialized,
    }
    if result is not None:
        payload["result"] = {
            "attemptedWindows": result.attempted_windows,
            "skippedProcessNames": result.skipped_process_names,
            "targetedProcessNames": result.targeted_process_names,
            "failures": result.failures,
            "summary": result.summary,
        }
    return payload


def command_state(_args: argparse.Namespace) -> None:
    _json(_state_payload())


def command_toggle(args: argparse.Namespace) -> None:
    process_name = args.process_name.strip()
    if not process_name:
        raise ValueError("process name is required")

    config = load_config()
    current = {name.lower(): name for name in config["allowlist_process_names"]}
    key = process_name.lower()
    if key in current:
        current.pop(key)
        message = f"已取消保留 {process_name}"
    else:
        current[key] = process_name
        message = f"已保留 {process_name}"
    config["allowlist_process_names"] = sorted(current.values(), key=str.lower)
    save_config(config)
    _json(_state_payload(message=message))


def command_clean(args: argparse.Namespace) -> None:
    config = load_config()
    windows = _filtered_windows()
    if args.scope == "foreground":
        result = close_non_allowlisted_windows(
            windows,
            config["allowlist_process_names"],
            include_background=False,
            include_foreground=True,
        )
    elif args.scope == "background":
        result = close_non_allowlisted_windows(
            windows,
            config["allowlist_process_names"],
            include_background=True,
            include_foreground=False,
        )
    else:
        result = close_non_allowlisted_windows(
            windows,
            config["allowlist_process_names"],
            include_background=True,
            include_foreground=True,
        )
    _json(_state_payload(message=result.summary, result=result))


def command_close_app(args: argparse.Namespace) -> None:
    process_name = args.process_name.strip()
    if not process_name:
        raise ValueError("process name is required")
    windows = _filtered_windows()
    result = close_selected_windows(
        windows,
        [process_name],
        include_background=args.scope in {"background", "all"},
        include_foreground=args.scope in {"foreground", "all"},
    )
    _json(_state_payload(message=result.summary, result=result))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app_cleaner.bridge")
    subparsers = parser.add_subparsers(dest="command", required=True)

    state = subparsers.add_parser("state")
    state.set_defaults(func=command_state)

    toggle = subparsers.add_parser("toggle")
    toggle.add_argument("process_name")
    toggle.set_defaults(func=command_toggle)

    clean = subparsers.add_parser("clean")
    clean.add_argument("scope", choices=["foreground", "background", "all"])
    clean.set_defaults(func=command_clean)

    close_app = subparsers.add_parser("close-app")
    close_app.add_argument("process_name")
    close_app.add_argument("scope", choices=["foreground", "background", "all"], default="all", nargs="?")
    close_app.set_defaults(func=command_close_app)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except Exception as exc:  # pragma: no cover - CLI boundary
        _safe_error(exc)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
