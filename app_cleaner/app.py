from __future__ import annotations

import os
import tkinter as tk
from tkinter import messagebox

from .autostart import is_autostart_enabled, set_autostart
from .config import load_config, save_config
from .desktop_apps import (
    AppCandidate,
    close_non_allowlisted_windows,
    close_selected_windows,
    enumerate_desktop_windows,
    group_apps,
)
from .hotkey import HotkeyParseError, hotkey_from_config, hotkey_to_dict, parse_hotkey_string
from .tray import TrayHost
from .electron_boost import ElectronBoostWindow
from .ui import SettingsWindow


class AppController:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.withdraw()
        self.root.title("桌面应用清理器")
        self.root.protocol("WM_DELETE_WINDOW", self.exit_app)

        self.config = load_config()
        self.config["autostart_enabled"] = is_autostart_enabled()
        self.status_text = "等待操作"
        self.current_windows = []
        self.current_apps: list[AppCandidate] = []
        self.last_close_result = None
        self.boost_window: ElectronBoostWindow | None = None
        self.settings_window: SettingsWindow | None = None

        self.tray = TrayHost(
            root,
            on_clean_now=self.clean_now,
            on_open_settings=self.show_settings,
            on_refresh_apps=self.refresh_apps,
            on_toggle_autostart=self.toggle_autostart,
            on_exit=self.exit_app,
            autostart_enabled_supplier=lambda: self.config["autostart_enabled"],
        )

        hotkey_spec = hotkey_from_config(self.config.get("hotkey"))
        if hotkey_spec is not None:
            self.tray.update_hotkey(hotkey_spec)
        self.refresh_apps()
        self.boost_window = ElectronBoostWindow()

        if self.config.get("minimize_to_tray_on_launch", True) and hotkey_spec is not None:
            self.root.after(200, self.root.withdraw)
        else:
            self.root.after(200, self.show_settings)

    @property
    def hotkey_display(self) -> str:
        hotkey_spec = hotkey_from_config(self.config.get("hotkey"))
        return hotkey_spec.display if hotkey_spec else ""

    def refresh_apps(self) -> None:
        self.current_windows = enumerate_desktop_windows(os.getpid())
        self.current_apps = group_apps(self.current_windows)
        self.status_text = f"当前检测到 {len(self.current_apps)} 个桌面应用"
        if self.settings_window is not None:
            self.settings_window.refresh(
                self.current_apps,
                self.config["allowlist_process_names"],
                self.status_text,
            )
        if self.boost_window is not None:
            self.boost_window.refresh()

    def clean_now(self) -> None:
        self.refresh_apps()
        result = close_non_allowlisted_windows(
            self.current_windows,
            self.config["allowlist_process_names"],
            include_background=self.config["cleanup_mode"] == "foreground_and_background",
        )
        self.last_close_result = result
        self.status_text = result.summary
        if self.settings_window is not None:
            self.settings_window.refresh(
                self.current_apps,
                self.config["allowlist_process_names"],
                self.status_text,
            )
        if self.boost_window is not None:
            self.boost_window.refresh()

    def clean_foreground_now(self) -> None:
        self.refresh_apps()
        result = close_non_allowlisted_windows(
            self.current_windows,
            self.config["allowlist_process_names"],
            include_background=False,
            include_foreground=True,
        )
        self.last_close_result = result
        self.status_text = result.summary
        if self.settings_window is not None:
            self.settings_window.refresh(
                self.current_apps,
                self.config["allowlist_process_names"],
                self.status_text,
            )
        if self.boost_window is not None:
            self.boost_window.refresh()

    def clean_background_now(self) -> None:
        self.refresh_apps()
        result = close_non_allowlisted_windows(
            self.current_windows,
            self.config["allowlist_process_names"],
            include_background=True,
            include_foreground=False,
        )
        self.last_close_result = result
        self.status_text = result.summary
        if self.settings_window is not None:
            self.settings_window.refresh(
                self.current_apps,
                self.config["allowlist_process_names"],
                self.status_text,
            )
        if self.boost_window is not None:
            self.boost_window.refresh()

    def close_selected_apps(self, process_names: list[str]) -> None:
        if not process_names:
            self.status_text = "未选择任何应用"
        else:
            self.refresh_apps()
            result = close_selected_windows(self.current_windows, process_names)
            self.last_close_result = result
            self.status_text = result.summary
        if self.settings_window is not None:
            self.settings_window.refresh(
                self.current_apps,
                self.config["allowlist_process_names"],
                self.status_text,
            )
        if self.boost_window is not None:
            self.boost_window.refresh()

    def show_settings(self) -> None:
        if self.settings_window is None:
            self.settings_window = SettingsWindow(self)
        self.settings_window.refresh(
            self.current_apps,
            self.config["allowlist_process_names"],
            self.status_text,
        )
        self.settings_window.show()

    def apply_settings(
        self,
        *,
        hotkey_text: str,
        allowlist_process_names: list[str],
        autostart_enabled: bool,
        minimize_to_tray_on_launch: bool,
        cleanup_mode: str,
    ) -> None:
        hotkey_spec = None
        if hotkey_text:
            hotkey_spec = parse_hotkey_string(hotkey_text)
        else:
            raise HotkeyParseError("请输入全局快捷键。")

        self.tray.update_hotkey(hotkey_spec)
        self.config["hotkey"] = hotkey_to_dict(hotkey_spec)
        self.config["allowlist_process_names"] = allowlist_process_names
        self.config["autostart_enabled"] = bool(autostart_enabled)
        self.config["minimize_to_tray_on_launch"] = bool(minimize_to_tray_on_launch)
        self.config["cleanup_mode"] = cleanup_mode
        set_autostart(self.config["autostart_enabled"])
        save_config(self.config)
        self.status_text = "设置已保存"

    def add_allowlist_entries(self, process_names: list[str]) -> None:
        merged = {name for name in self.config["allowlist_process_names"]}
        merged.update(name for name in process_names if name)
        self.config["allowlist_process_names"] = sorted(merged, key=str.lower)
        save_config(self.config)
        self.status_text = "已加入白名单"
        if self.settings_window is not None:
            self.settings_window.refresh(
                self.current_apps,
                self.config["allowlist_process_names"],
                self.status_text,
            )
        if self.boost_window is not None:
            self.boost_window.refresh()

    def remove_allowlist_entries(self, process_names: list[str]) -> None:
        to_remove = {name.lower() for name in process_names}
        self.config["allowlist_process_names"] = [
            name
            for name in self.config["allowlist_process_names"]
            if name.lower() not in to_remove
        ]
        save_config(self.config)
        self.status_text = "已移出白名单"
        if self.settings_window is not None:
            self.settings_window.refresh(
                self.current_apps,
                self.config["allowlist_process_names"],
                self.status_text,
            )
        if self.boost_window is not None:
            self.boost_window.refresh()

    def toggle_autostart(self) -> None:
        new_value = not self.config["autostart_enabled"]
        try:
            set_autostart(new_value)
        except OSError as exc:
            messagebox.showerror("开机启动切换失败", str(exc))
            return
        self.config["autostart_enabled"] = new_value
        save_config(self.config)
        self.status_text = "已启用开机启动" if new_value else "已关闭开机启动"
        if self.settings_window is not None:
            self.settings_window.refresh(
                self.current_apps,
                self.config["allowlist_process_names"],
                self.status_text,
            )
        if self.boost_window is not None:
            self.boost_window.refresh()

    def exit_app(self) -> None:
        if self.settings_window is not None:
            self.settings_window.destroy()
            self.settings_window = None
        if self.boost_window is not None:
            self.boost_window.destroy()
            self.boost_window = None
        self.tray.destroy()
        self.root.quit()
