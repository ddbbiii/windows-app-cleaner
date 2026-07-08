from __future__ import annotations

import ctypes
import os
import winreg
from dataclasses import dataclass, field
from typing import Iterable

from . import win32_api as win32


EXCLUDED_CLASSES = {
    "Progman",
    "WorkerW",
    "Shell_TrayWnd",
    "Shell_SecondaryTrayWnd",
    "DV2ControlHost",
    "Windows.UI.Core.CoreWindow",
}

EXCLUDED_TRAY_PROCESS_NAMES = {
    "explorer.exe",
    "shellexperiencehost.exe",
    "systemsettings.exe",
    "textinputhost.exe",
}

KNOWN_FOLDER_PREFIXES = {
    "{6d809377-6af0-444b-8957-a3773f02200e}": "ProgramFiles",
    "{7c5a40ef-a0fb-4bfc-874a-c0f2e0b9fa8e}": "ProgramFiles(x86)",
    "{1ac14e77-02e7-4e5d-b744-2eb1ae5198b7}": "SystemRoot",
    "{f38bf404-1d43-42f2-9305-67de0b28fc23}": "SystemRoot",
}


@dataclass(slots=True)
class WindowCandidate:
    hwnd: int
    pid: int
    process_name: str
    title: str
    exe_path: str
    class_name: str
    is_background: bool


@dataclass(slots=True)
class AppCandidate:
    process_name: str
    exe_path: str
    window_count: int = 0
    foreground_window_count: int = 0
    background_window_count: int = 0
    titles: list[str] = field(default_factory=list)

    @property
    def display_title(self) -> str:
        if not self.titles:
            return self.process_name
        first = self.titles[0]
        if self.window_count <= 1:
            return first
        return f"{first} 等 {self.window_count} 个窗口"

    @property
    def state_label(self) -> str:
        if self.foreground_window_count and self.background_window_count:
            return "前台+后台"
        if self.background_window_count:
            return "后台"
        return "前台"


@dataclass(slots=True)
class CloseResult:
    attempted_windows: int
    skipped_process_names: list[str]
    targeted_process_names: list[str]
    failures: list[str]

    @property
    def summary(self) -> str:
        targeted = "、".join(self.targeted_process_names) if self.targeted_process_names else "无"
        skipped = "、".join(self.skipped_process_names) if self.skipped_process_names else "无"
        failed = "；".join(self.failures) if self.failures else "无"
        return (
            f"已发送关闭请求: {self.attempted_windows} 个窗口 | "
            f"目标进程: {targeted} | 保留名单: {skipped} | 失败: {failed}"
        )


def enumerate_desktop_windows(current_pid: int) -> list[WindowCandidate]:
    shell_window = win32.user32.GetShellWindow()
    results: list[WindowCandidate] = []

    @win32.EnumWindowsProc
    def callback(hwnd: int, _lparam: int) -> bool:
        if hwnd == shell_window:
            return True
        if not win32.user32.IsWindowVisible(hwnd):
            return True
        if win32.user32.GetWindow(hwnd, win32.GW_OWNER):
            return True
        if win32.is_window_cloaked(hwnd):
            return True

        ex_style = win32.user32.GetWindowLongPtrW(hwnd, win32.GWL_EXSTYLE)
        if ex_style & win32.WS_EX_TOOLWINDOW and not ex_style & win32.WS_EX_APPWINDOW:
            return True

        title = win32.get_window_text(hwnd)
        if not title:
            return True

        class_name = win32.get_class_name(hwnd)
        if class_name in EXCLUDED_CLASSES:
            return True

        pid = ctypes.c_ulong()
        win32.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == 0 or pid.value == current_pid:
            return True

        exe_path = win32.query_process_image_path(pid.value)
        process_name = os.path.basename(exe_path) if exe_path else f"pid-{pid.value}"

        results.append(
            WindowCandidate(
                hwnd=hwnd,
                pid=pid.value,
                process_name=process_name,
                title=title,
                exe_path=exe_path,
                class_name=class_name,
                is_background=False,
            )
        )
        return True

    win32.user32.EnumWindows(callback, 0)
    existing_hwnds = {item.hwnd for item in results}
    for item in enumerate_tray_windows(current_pid):
        if item.hwnd not in existing_hwnds:
            results.append(item)
            existing_hwnds.add(item.hwnd)
    return results


def enumerate_tray_windows(current_pid: int) -> list[WindowCandidate]:
    results: list[WindowCandidate] = []
    seen_hwnds: set[int] = set()

    for toolbar in _tray_toolbars():
        for hwnd in _tray_icon_owner_windows(toolbar):
            if hwnd in seen_hwnds:
                continue
            seen_hwnds.add(hwnd)
            if not win32.user32.IsWindow(hwnd):
                continue

            pid = ctypes.c_ulong()
            win32.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value == 0 or pid.value == current_pid:
                continue

            exe_path = win32.query_process_image_path(pid.value)
            process_name = os.path.basename(exe_path) if exe_path else f"pid-{pid.value}"
            if process_name.lower() in EXCLUDED_TRAY_PROCESS_NAMES:
                continue

            title = win32.get_window_text(hwnd) or f"{process_name} (托盘)"
            results.append(
                WindowCandidate(
                    hwnd=hwnd,
                    pid=pid.value,
                    process_name=process_name,
                    title=title,
                    exe_path=exe_path,
                    class_name=win32.get_class_name(hwnd),
                    is_background=True,
                )
            )
    for item in _registry_tray_windows(current_pid):
        if item.hwnd not in seen_hwnds:
            results.append(item)
            seen_hwnds.add(item.hwnd)
    return results


def _registry_tray_windows(current_pid: int) -> list[WindowCandidate]:
    running = _running_processes_by_name()
    results: list[WindowCandidate] = []
    seen_pids: set[int] = set()

    for configured_path in _promoted_notify_icon_paths():
        process_name = os.path.basename(configured_path)
        if not process_name or process_name.lower() in EXCLUDED_TRAY_PROCESS_NAMES:
            continue
        for pid, exe_path in running.get(process_name.lower(), []):
            if pid == current_pid or pid in seen_pids:
                continue
            if exe_path and not _same_executable(configured_path, exe_path):
                continue
            hwnd = _hidden_owner_window_for_pid(pid)
            if not hwnd:
                continue
            seen_pids.add(pid)
            results.append(
                WindowCandidate(
                    hwnd=hwnd,
                    pid=pid,
                    process_name=os.path.basename(exe_path) if exe_path else process_name,
                    title=f"{process_name} (托盘)",
                    exe_path=exe_path or configured_path,
                    class_name=win32.get_class_name(hwnd),
                    is_background=True,
                )
            )
    return results


def _promoted_notify_icon_paths() -> list[str]:
    paths: list[str] = []
    try:
        root = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\NotifyIconSettings")
    except OSError:
        return paths

    with root:
        try:
            subkey_count = winreg.QueryInfoKey(root)[0]
        except OSError:
            return paths
        for index in range(subkey_count):
            try:
                subkey_name = winreg.EnumKey(root, index)
                subkey = winreg.OpenKey(root, subkey_name)
            except OSError:
                continue
            with subkey:
                promoted = _query_registry_dword(subkey, "IsPromoted")
                if promoted is None:
                    promoted = _query_registry_dword(subkey, "isPromoted")
                if promoted != 1:
                    continue
                try:
                    raw_path, _value_type = winreg.QueryValueEx(subkey, "ExecutablePath")
                except OSError:
                    continue
                resolved = _resolve_notify_icon_path(str(raw_path))
                if resolved:
                    paths.append(resolved)
    return paths


def _query_registry_dword(key, name: str) -> int | None:
    try:
        value, _value_type = winreg.QueryValueEx(key, name)
    except OSError:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _resolve_notify_icon_path(raw_path: str) -> str:
    path = raw_path.strip()
    if not path:
        return ""
    if path.startswith("{"):
        prefix, sep, rest = path.partition("\\")
        env_name = KNOWN_FOLDER_PREFIXES.get(prefix.lower())
        if env_name and sep:
            if env_name == "SystemRoot" and prefix.lower() == "{1ac14e77-02e7-4e5d-b744-2eb1ae5198b7}":
                base = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32")
            else:
                base = os.environ.get(env_name, "")
            if base:
                path = os.path.join(base, rest)
    return os.path.normcase(os.path.abspath(os.path.expandvars(path)))


def _same_executable(left: str, right: str) -> bool:
    left_norm = os.path.normcase(os.path.abspath(os.path.expandvars(left)))
    right_norm = os.path.normcase(os.path.abspath(os.path.expandvars(right)))
    if left_norm == right_norm:
        return True
    return os.path.basename(left_norm).lower() == os.path.basename(right_norm).lower()


def _running_processes_by_name() -> dict[str, list[tuple[int, str]]]:
    snapshot = win32.kernel32.CreateToolhelp32Snapshot(win32.TH32CS_SNAPPROCESS, 0)
    invalid_handle = ctypes.c_void_p(-1).value
    if not snapshot or snapshot == invalid_handle:
        return {}

    processes: dict[str, list[tuple[int, str]]] = {}
    try:
        entry = win32.PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(win32.PROCESSENTRY32W)
        has_item = bool(win32.kernel32.Process32FirstW(snapshot, ctypes.byref(entry)))
        while has_item:
            pid = int(entry.th32ProcessID)
            name = entry.szExeFile.strip()
            if pid and name:
                exe_path = win32.query_process_image_path(pid)
                process_name = os.path.basename(exe_path) if exe_path else name
                processes.setdefault(process_name.lower(), []).append((pid, exe_path))
            has_item = bool(win32.kernel32.Process32NextW(snapshot, ctypes.byref(entry)))
    finally:
        win32.kernel32.CloseHandle(snapshot)
    return processes


def _hidden_owner_window_for_pid(target_pid: int) -> int:
    shell_window = win32.user32.GetShellWindow()
    hidden_windows: list[int] = []

    @win32.EnumWindowsProc
    def callback(hwnd: int, _lparam: int) -> bool:
        if hwnd == shell_window:
            return True
        pid = ctypes.c_ulong()
        win32.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value != target_pid:
            return True
        class_name = win32.get_class_name(hwnd)
        if class_name in EXCLUDED_CLASSES:
            return True
        if not win32.user32.IsWindowVisible(hwnd):
            hidden_windows.append(hwnd)
        return True

    win32.user32.EnumWindows(callback, 0)
    return hidden_windows[0] if hidden_windows else 0


def _tray_toolbars() -> list[int]:
    roots = [
        win32.user32.FindWindowW("Shell_TrayWnd", None),
        win32.user32.FindWindowW("NotifyIconOverflowWindow", None),
    ]
    toolbars: list[int] = []
    seen: set[int] = set()

    for root in roots:
        if not root:
            continue
        search_root = root
        tray_notify = win32.user32.FindWindowExW(root, 0, "TrayNotifyWnd", None)
        if tray_notify:
            search_root = tray_notify
        for toolbar in _child_windows_by_class(search_root, "ToolbarWindow32"):
            if toolbar not in seen:
                toolbars.append(toolbar)
                seen.add(toolbar)
    return toolbars


def _child_windows_by_class(root: int, class_name: str) -> list[int]:
    results: list[int] = []

    @win32.EnumChildProc
    def callback(hwnd: int, _lparam: int) -> bool:
        if win32.get_class_name(hwnd) == class_name:
            results.append(hwnd)
        return True

    win32.user32.EnumChildWindows(root, callback, 0)
    return results


def _tray_icon_owner_windows(toolbar: int) -> list[int]:
    toolbar_pid = ctypes.c_ulong()
    win32.user32.GetWindowThreadProcessId(toolbar, ctypes.byref(toolbar_pid))
    if not toolbar_pid.value:
        return []

    access = (
        win32.PROCESS_QUERY_LIMITED_INFORMATION
        | win32.PROCESS_VM_OPERATION
        | win32.PROCESS_VM_READ
        | win32.PROCESS_VM_WRITE
    )
    process = win32.kernel32.OpenProcess(access, False, toolbar_pid.value)
    if not process:
        return []

    remote_button = None
    try:
        button_size = ctypes.sizeof(win32.TBBUTTON)
        remote_button = win32.kernel32.VirtualAllocEx(
            process,
            None,
            button_size,
            win32.MEM_COMMIT | win32.MEM_RESERVE,
            win32.PAGE_READWRITE,
        )
        if not remote_button:
            return []

        count = int(win32.user32.SendMessageW(toolbar, win32.TB_BUTTONCOUNT, 0, 0))
        owner_windows: list[int] = []
        for index in range(max(0, count)):
            if not win32.user32.SendMessageW(toolbar, win32.TB_GETBUTTON, index, int(remote_button)):
                continue

            button = win32.TBBUTTON()
            bytes_read = ctypes.c_size_t()
            if not win32.kernel32.ReadProcessMemory(
                process,
                ctypes.c_void_p(int(remote_button)),
                ctypes.cast(ctypes.byref(button), win32.LPVOID),
                button_size,
                ctypes.byref(bytes_read),
            ):
                continue
            if not button.dwData:
                continue

            tray_hwnd = ctypes.c_size_t()
            bytes_read = ctypes.c_size_t()
            if not win32.kernel32.ReadProcessMemory(
                process,
                ctypes.c_void_p(button.dwData),
                ctypes.cast(ctypes.byref(tray_hwnd), win32.LPVOID),
                ctypes.sizeof(tray_hwnd),
                ctypes.byref(bytes_read),
            ):
                continue
            if tray_hwnd.value:
                owner_windows.append(int(tray_hwnd.value))
        return owner_windows
    finally:
        if remote_button:
            win32.kernel32.VirtualFreeEx(process, remote_button, 0, win32.MEM_RELEASE)
        win32.kernel32.CloseHandle(process)


def group_apps(windows: Iterable[WindowCandidate]) -> list[AppCandidate]:
    grouped: dict[str, AppCandidate] = {}
    for item in windows:
        key = item.process_name.lower()
        existing = grouped.get(key)
        if existing is None:
            existing = AppCandidate(
                process_name=item.process_name,
                exe_path=item.exe_path,
            )
            grouped[key] = existing
        existing.window_count += 1
        if item.is_background:
            existing.background_window_count += 1
        else:
            existing.foreground_window_count += 1
        if item.title not in existing.titles:
            existing.titles.append(item.title)
    return sorted(grouped.values(), key=lambda item: (item.process_name.lower(), item.display_title.lower()))


def close_non_allowlisted_windows(
    windows: Iterable[WindowCandidate],
    allowlist_process_names: Iterable[str],
    *,
    include_background: bool,
    include_foreground: bool = True,
) -> CloseResult:
    allowlist = {name.lower() for name in allowlist_process_names}
    targeted_processes: set[str] = set()
    skipped_processes: set[str] = set()
    failures: list[str] = []
    attempted = 0

    for item in windows:
        if not item.is_background and not include_foreground:
            continue
        if item.is_background and not include_background:
            continue

        normalized_name = item.process_name.lower()
        if normalized_name in allowlist:
            skipped_processes.add(item.process_name)
            continue

        if win32.user32.PostMessageW(item.hwnd, win32.WM_CLOSE, 0, 0):
            attempted += 1
            targeted_processes.add(item.process_name)
        else:
            error = win32.get_last_error_message()
            failures.append(f"{item.process_name}({item.title}): {error}")

    return CloseResult(
        attempted_windows=attempted,
        skipped_process_names=sorted(skipped_processes, key=str.lower),
        targeted_process_names=sorted(targeted_processes, key=str.lower),
        failures=failures,
    )


def close_selected_windows(
    windows: Iterable[WindowCandidate],
    process_names: Iterable[str],
    *,
    include_background: bool = True,
    include_foreground: bool = True,
) -> CloseResult:
    selected = {name.lower() for name in process_names}
    targeted_processes: set[str] = set()
    failures: list[str] = []
    attempted = 0

    for item in windows:
        if item.process_name.lower() not in selected:
            continue
        if not item.is_background and not include_foreground:
            continue
        if item.is_background and not include_background:
            continue
        if win32.user32.PostMessageW(item.hwnd, win32.WM_CLOSE, 0, 0):
            attempted += 1
            targeted_processes.add(item.process_name)
        else:
            error = win32.get_last_error_message()
            failures.append(f"{item.process_name}({item.title}): {error}")

    return CloseResult(
        attempted_windows=attempted,
        skipped_process_names=[],
        targeted_process_names=sorted(targeted_processes, key=str.lower),
        failures=failures,
    )
