from __future__ import annotations

import sys
from pathlib import Path

from . import win32_api as win32


AUTOSTART_FILENAME = "desktop-app-cleaner.vbs"


def get_autostart_file() -> Path:
    return win32.get_startup_folder() / AUTOSTART_FILENAME


def is_autostart_enabled() -> bool:
    return get_autostart_file().exists()


def _resolve_launcher() -> tuple[str, str]:
    if getattr(sys, "frozen", False):
        exe_path = Path(sys.executable).resolve()
        return str(exe_path), ""

    script_path = Path(sys.argv[0]).resolve()
    python_exe = Path(sys.executable).resolve()
    pythonw_exe = python_exe.with_name("pythonw.exe")
    launcher = pythonw_exe if pythonw_exe.exists() else python_exe
    return str(launcher), f'"{script_path}"'


def set_autostart(enabled: bool) -> None:
    target = get_autostart_file()
    if not enabled:
        if target.exists():
            target.unlink()
        return

    target.parent.mkdir(parents=True, exist_ok=True)
    launcher, argument = _resolve_launcher()
    command = f'"{launcher}"'
    if argument:
        command = f'{command} {argument}'

    script = "\n".join(
        [
            'Set WshShell = CreateObject("WScript.Shell")',
            f'WshShell.Run "{command.replace(chr(34), chr(34) * 2)}", 0',
        ]
    )
    target.write_text(script, encoding="utf-8")

