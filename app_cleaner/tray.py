from __future__ import annotations

import ctypes
from collections.abc import Callable

from . import win32_api as win32
from .hotkey import HotkeySpec


CMD_CLEAN_NOW = 1001
CMD_OPEN_SETTINGS = 1002
CMD_REFRESH_APPS = 1003
CMD_TOGGLE_AUTOSTART = 1004
CMD_EXIT = 1005
TRAY_CALLBACK_MESSAGE = win32.WM_APP + 1
HOTKEY_ID = 1


class TrayHost:
    _instances: dict[int, "TrayHost"] = {}

    def __init__(
        self,
        root,
        *,
        on_clean_now: Callable[[], None],
        on_open_settings: Callable[[], None],
        on_refresh_apps: Callable[[], None],
        on_toggle_autostart: Callable[[], None],
        on_exit: Callable[[], None],
        autostart_enabled_supplier: Callable[[], bool],
    ) -> None:
        self.root = root
        self.on_clean_now = on_clean_now
        self.on_open_settings = on_open_settings
        self.on_refresh_apps = on_refresh_apps
        self.on_toggle_autostart = on_toggle_autostart
        self.on_exit = on_exit
        self.autostart_enabled_supplier = autostart_enabled_supplier
        self.class_name = "DesktopAppCleanerTrayWindow"
        self.instance_handle = ctypes.windll.kernel32.GetModuleHandleW(None)
        self.wndproc = win32.WNDPROC(self._wndproc)
        self.hwnd = self._create_window()
        self.icon_data = self._create_icon_data()
        self.registered_hotkey: HotkeySpec | None = None
        self._icon_added = False
        self._add_tray_icon()
        self._schedule_pump()

    def _create_window(self) -> int:
        wnd_class = win32.WNDCLASSW()
        wnd_class.lpfnWndProc = self.wndproc
        wnd_class.lpszClassName = self.class_name
        wnd_class.hInstance = self.instance_handle
        wnd_class.hIcon = win32.user32.LoadIconW(None, win32.make_int_resource(win32.IDI_APPLICATION))
        atom = win32.user32.RegisterClassW(ctypes.byref(wnd_class))
        if atom == 0:
            raise OSError(win32.get_last_error_message())

        hwnd = win32.user32.CreateWindowExW(
            0,
            self.class_name,
            self.class_name,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            self.instance_handle,
            None,
        )
        if not hwnd:
            raise OSError(win32.get_last_error_message())
        self._instances[hwnd] = self
        return hwnd

    def _create_icon_data(self) -> win32.NOTIFYICONDATAW:
        data = win32.NOTIFYICONDATAW()
        data.cbSize = ctypes.sizeof(win32.NOTIFYICONDATAW)
        data.hWnd = self.hwnd
        data.uID = 1
        data.uFlags = win32.NIF_ICON | win32.NIF_MESSAGE | win32.NIF_TIP | win32.NIF_SHOWTIP
        data.uCallbackMessage = TRAY_CALLBACK_MESSAGE
        data.hIcon = win32.user32.LoadIconW(None, win32.make_int_resource(win32.IDI_APPLICATION))
        data.szTip = "桌面应用清理器"
        data.uTimeoutOrVersion = win32.NOTIFYICON_VERSION_4
        return data

    def _add_tray_icon(self) -> None:
        if not win32.shell32.Shell_NotifyIconW(win32.NIM_ADD, ctypes.byref(self.icon_data)):
            raise OSError(win32.get_last_error_message())
        win32.shell32.Shell_NotifyIconW(win32.NIM_SETVERSION, ctypes.byref(self.icon_data))
        self._icon_added = True

    def _schedule_pump(self) -> None:
        self._pump_messages()
        self.root.after(50, self._schedule_pump)

    def _pump_messages(self) -> None:
        message = win32.MSG()
        while win32.user32.PeekMessageW(ctypes.byref(message), self.hwnd, 0, 0, win32.PM_REMOVE):
            win32.user32.TranslateMessage(ctypes.byref(message))
            win32.user32.DispatchMessageW(ctypes.byref(message))

    def update_hotkey(self, spec: HotkeySpec | None) -> None:
        if self.registered_hotkey is not None:
            win32.user32.UnregisterHotKey(self.hwnd, HOTKEY_ID)
            self.registered_hotkey = None
        if spec is None:
            return
        if not win32.user32.RegisterHotKey(self.hwnd, HOTKEY_ID, spec.modifiers, spec.vk):
            raise OSError(win32.get_last_error_message())
        self.registered_hotkey = spec

    def destroy(self) -> None:
        if self.registered_hotkey is not None:
            win32.user32.UnregisterHotKey(self.hwnd, HOTKEY_ID)
            self.registered_hotkey = None
        if self._icon_added:
            win32.shell32.Shell_NotifyIconW(win32.NIM_DELETE, ctypes.byref(self.icon_data))
            self._icon_added = False
        if self.hwnd:
            self._instances.pop(self.hwnd, None)
            win32.user32.DestroyWindow(self.hwnd)
            self.hwnd = 0
        win32.user32.UnregisterClassW(self.class_name, self.instance_handle)

    def _show_menu(self) -> None:
        menu = win32.user32.CreatePopupMenu()
        autostart_label = "关闭开机启动" if self.autostart_enabled_supplier() else "启用开机启动"
        win32.user32.AppendMenuW(menu, win32.MF_STRING, CMD_CLEAN_NOW, "立即清理")
        win32.user32.AppendMenuW(menu, win32.MF_STRING, CMD_OPEN_SETTINGS, "打开设置")
        win32.user32.AppendMenuW(menu, win32.MF_STRING, CMD_REFRESH_APPS, "刷新当前应用列表")
        win32.user32.AppendMenuW(menu, win32.MF_STRING, CMD_TOGGLE_AUTOSTART, autostart_label)
        win32.user32.AppendMenuW(menu, win32.MF_SEPARATOR, 0, None)
        win32.user32.AppendMenuW(menu, win32.MF_STRING, CMD_EXIT, "退出")
        point = win32.POINT()
        win32.user32.GetCursorPos(ctypes.byref(point))
        win32.user32.SetForegroundWindow(self.hwnd)
        win32.user32.TrackPopupMenu(
            menu,
            win32.TPM_LEFTALIGN | win32.TPM_BOTTOMALIGN | win32.TPM_RIGHTBUTTON,
            point.x,
            point.y,
            0,
            self.hwnd,
            None,
        )
        win32.user32.DestroyMenu(menu)

    def _handle_command(self, command_id: int) -> None:
        if command_id == CMD_CLEAN_NOW:
            self.on_clean_now()
        elif command_id == CMD_OPEN_SETTINGS:
            self.on_open_settings()
        elif command_id == CMD_REFRESH_APPS:
            self.on_refresh_apps()
        elif command_id == CMD_TOGGLE_AUTOSTART:
            self.on_toggle_autostart()
        elif command_id == CMD_EXIT:
            self.on_exit()

    def _wndproc(self, hwnd: int, message: int, wparam: int, lparam: int) -> int:
        if message == TRAY_CALLBACK_MESSAGE:
            event_id = lparam & 0xFFFF
            if event_id in {win32.WM_RBUTTONUP, win32.WM_CONTEXTMENU}:
                self._show_menu()
                return 0
            if event_id in {
                win32.WM_LBUTTONUP,
                win32.WM_LBUTTONDBLCLK,
                win32.NIN_SELECT,
                win32.NIN_KEYSELECT,
            }:
                self.on_open_settings()
                return 0
        elif message == win32.WM_COMMAND:
            self._handle_command(wparam & 0xFFFF)
            return 0
        elif message == win32.WM_HOTKEY and wparam == HOTKEY_ID:
            self.on_clean_now()
            return 0
        elif message == win32.WM_DESTROY:
            return 0
        return win32.user32.DefWindowProcW(hwnd, message, wparam, lparam)
