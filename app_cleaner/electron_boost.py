from __future__ import annotations

import ctypes
import os
import subprocess
from pathlib import Path
from typing import Any

from .config import APP_DIR


CREATE_NO_WINDOW = 0x08000000
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
JobObjectExtendedLimitInformation = 9


class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", ctypes.c_uint32),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", ctypes.c_uint32),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", ctypes.c_uint32),
        ("SchedulingClass", ctypes.c_uint32),
    ]


class IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_ulonglong),
        ("WriteOperationCount", ctypes.c_ulonglong),
        ("OtherOperationCount", ctypes.c_ulonglong),
        ("ReadTransferCount", ctypes.c_ulonglong),
        ("WriteTransferCount", ctypes.c_ulonglong),
        ("OtherTransferCount", ctypes.c_ulonglong),
    ]


class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
kernel32.CreateJobObjectW.restype = ctypes.c_void_p
kernel32.SetInformationJobObject.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32]
kernel32.SetInformationJobObject.restype = ctypes.c_int
kernel32.AssignProcessToJobObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
kernel32.AssignProcessToJobObject.restype = ctypes.c_int
kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
kernel32.CloseHandle.restype = ctypes.c_int


def _raise_last_error() -> None:
    raise ctypes.WinError(ctypes.get_last_error())


def _create_kill_on_close_job() -> int:
    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        _raise_last_error()
    info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    ok = kernel32.SetInformationJobObject(
        job,
        JobObjectExtendedLimitInformation,
        ctypes.byref(info),
        ctypes.sizeof(info),
    )
    if not ok:
        kernel32.CloseHandle(job)
        _raise_last_error()
    return int(job)


class ElectronBoostWindow:
    def __init__(self) -> None:
        self.process: subprocess.Popen | None = None
        self.job_handle: int | None = None
        self.start()

    def start(self) -> None:
        if self.process is not None and self.process.poll() is None:
            return

        electron_dir = APP_DIR / "electron"
        electron_cmd = self._electron_command(electron_dir)
        env = os.environ.copy()
        env.setdefault("PYTHONUTF8", "1")
        env["APP_CLEANER_ROOT"] = str(APP_DIR)
        env.setdefault("APP_CLEANER_PYTHON", self._python_executable())
        if self.job_handle is None:
            self.job_handle = _create_kill_on_close_job()
        self.process = subprocess.Popen(
            electron_cmd,
            cwd=electron_dir,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW,
        )
        self._assign_to_job(self.process)

    def refresh(self) -> None:
        self.start()

    def destroy(self) -> None:
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                subprocess.run(
                    ["taskkill.exe", "/PID", str(self.process.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                    creationflags=CREATE_NO_WINDOW,
                )
        self.process = None
        self._close_job()

    def _assign_to_job(self, process: subprocess.Popen[Any]) -> None:
        if self.job_handle is None:
            return
        if not kernel32.AssignProcessToJobObject(self.job_handle, int(process._handle)):
            # The app still works without the job; explicit exit will use taskkill as fallback.
            return

    def _close_job(self) -> None:
        if self.job_handle is not None:
            kernel32.CloseHandle(self.job_handle)
            self.job_handle = None

    @staticmethod
    def _electron_command(electron_dir: Path) -> list[str]:
        electron_exe = electron_dir / "node_modules" / "electron" / "dist" / "electron.exe"
        if electron_exe.exists():
            return [str(electron_exe), "."]
        local_cmd = electron_dir / "node_modules" / ".bin" / "electron.cmd"
        if local_cmd.exists():
            return [str(local_cmd), "."]
        return ["npm.cmd", "start", "--", "--launched-by-python"]

    @staticmethod
    def _python_executable() -> str:
        preferred = Path(r"E:\program\language\python\Python-3.11.0\python.exe")
        if preferred.exists():
            return str(preferred)
        return "python"
