"""Top-level window detection through ctypes (user32 / kernel32 / dwmapi).

Used by the "wait for window" actions. Works for any program, SAP GUI included,
without SAP GUI scripting.
"""
import ctypes
import os
import time
from ctypes import wintypes
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from .base import ActionResult, progress_bar

# SAP GUI session windows and modal popups use this class; dialogs like
# "Guardar como" are plain #32770 windows owned by the SAP process.
SAP_WINDOW_CLASS = "SAP_FRONTEND_SESSION"
SAP_PROCESSES = ("saplogon.exe", "sapgui.exe", "saplgpad.exe")
DIALOG_CLASS = "#32770"

# What a wait action does when its time limit runs out
ON_TIMEOUT_FAIL = "Marcar error"
ON_TIMEOUT_CONTINUE = "Continuar"
ON_TIMEOUT_ABORT = "Finalizar proceso con error"
ON_TIMEOUT_CHOICES = [ON_TIMEOUT_FAIL, ON_TIMEOUT_CONTINUE, ON_TIMEOUT_ABORT]

_IS_WINDOWS = os.name == "nt"

if _IS_WINDOWS:
    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    try:
        _dwmapi = ctypes.WinDLL("dwmapi")
    except OSError:
        _dwmapi = None

    _WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    _user32.EnumWindows.argtypes = [_WNDENUMPROC, wintypes.LPARAM]
    _user32.IsWindowVisible.argtypes = [wintypes.HWND]
    _user32.IsWindow.argtypes = [wintypes.HWND]
    _user32.IsIconic.argtypes = [wintypes.HWND]
    _user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    _user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    _user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    _user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    _user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    _user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
    _user32.GetWindow.restype = wintypes.HWND
    _user32.GetForegroundWindow.restype = wintypes.HWND
    _user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    _user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    _kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    _kernel32.OpenProcess.restype = wintypes.HANDLE
    _kernel32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    _kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

_GW_OWNER = 4
_SW_RESTORE = 9
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_DWMWA_CLOAKED = 14
_VK_MENU = 0x12
_KEYEVENTF_KEYUP = 0x2


@dataclass
class WindowInfo:
    hwnd: int
    title: str
    class_name: str
    pid: int
    process: str   # executable name in lower case, e.g. "saplogon.exe"
    owned: bool    # popups/dialogs are owned by their main window

    @property
    def is_sap(self) -> bool:
        return self.class_name == SAP_WINDOW_CLASS or self.process in SAP_PROCESSES

    def describe(self) -> str:
        return f"«{self.title or self.class_name}» ({self.process or '?'})"


def _text(fn, hwnd, size=512) -> str:
    buf = ctypes.create_unicode_buffer(size)
    fn(hwnd, buf, size)
    return buf.value


def window_title(hwnd: int) -> str:
    if not _IS_WINDOWS:
        return ""
    length = _user32.GetWindowTextLengthW(hwnd)
    return _text(_user32.GetWindowTextW, hwnd, max(length + 1, 2))


def window_exists(hwnd: int) -> bool:
    return bool(_IS_WINDOWS and _user32.IsWindow(hwnd) and _user32.IsWindowVisible(hwnd))


def _process_name(pid: int, cache: Dict[int, str]) -> str:
    if pid in cache:
        return cache[pid]
    name = ""
    handle = _kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if handle:
        try:
            buf = ctypes.create_unicode_buffer(1024)
            size = wintypes.DWORD(len(buf))
            if _kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                name = os.path.basename(buf.value).lower()
        finally:
            _kernel32.CloseHandle(handle)
    cache[pid] = name
    return name


def _is_cloaked(hwnd: int) -> bool:
    # Suspended UWP apps report as visible but are hidden by DWM
    if _dwmapi is None:
        return False
    cloaked = wintypes.DWORD(0)
    res = _dwmapi.DwmGetWindowAttribute(wintypes.HWND(hwnd), _DWMWA_CLOAKED,
                                        ctypes.byref(cloaked), ctypes.sizeof(cloaked))
    return res == 0 and cloaked.value != 0


def list_windows() -> List[WindowInfo]:
    """Visible top-level windows that a user could see, topmost first (Z-order)."""
    if not _IS_WINDOWS:
        return []
    own_pid = os.getpid()
    pid_cache: Dict[int, str] = {}
    found: List[WindowInfo] = []

    def _cb(hwnd, _):
        if not _user32.IsWindowVisible(hwnd) or _is_cloaked(hwnd):
            return True
        rect = wintypes.RECT()
        _user32.GetWindowRect(hwnd, ctypes.byref(rect))
        if rect.right - rect.left <= 0 or rect.bottom - rect.top <= 0:
            return True
        title = window_title(hwnd)
        class_name = _text(_user32.GetClassNameW, hwnd, 256)
        # Untitled windows are menus, tooltips and shell parts — except dialogs
        if not title.strip() and class_name != DIALOG_CLASS:
            return True
        pid = wintypes.DWORD(0)
        _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == own_pid:
            return True
        found.append(WindowInfo(
            hwnd=int(hwnd), title=title, class_name=class_name, pid=pid.value,
            process=_process_name(pid.value, pid_cache),
            owned=bool(_user32.GetWindow(hwnd, _GW_OWNER)),
        ))
        return True

    _user32.EnumWindows(_WNDENUMPROC(_cb), 0)
    return found


def foreground_hwnd() -> int:
    return int(_user32.GetForegroundWindow() or 0) if _IS_WINDOWS else 0


def focus_window(hwnd: int) -> bool:
    if not _IS_WINDOWS:
        return False
    if _user32.IsIconic(hwnd):
        _user32.ShowWindow(hwnd, _SW_RESTORE)
    # Windows only lets the foreground process change focus; a synthetic Alt lifts that lock
    _user32.keybd_event(_VK_MENU, 0, 0, 0)
    _user32.keybd_event(_VK_MENU, 0, _KEYEVENTF_KEYUP, 0)
    return bool(_user32.SetForegroundWindow(hwnd))


def matches_process(info: WindowInfo, process: str) -> bool:
    process = process.strip().lower()
    if not process:
        return True
    if not process.endswith(".exe"):
        process += ".exe"
    return info.process == process


def timeout_result(params: Dict, msg: str, variables: Dict, hint: str = "") -> ActionResult:
    """Result of a wait whose time limit ran out, according to its "on_timeout" option."""
    choice = params.get("on_timeout", ON_TIMEOUT_FAIL)
    if choice == ON_TIMEOUT_CONTINUE:
        return ActionResult.success(output=f"{msg} — se continúa", variables=variables)
    return ActionResult.failure(msg + hint, abort=choice == ON_TIMEOUT_ABORT)


# Waits shorter than this end before a progress line is worth reading
PROGRESS_MIN_SECONDS = 2


def wait_until(context: Dict, check: Callable[[], object], timeout: float, interval: float = 0.25):
    """Poll `check()` until it returns something truthy or `timeout` seconds pass.

    Paused time does not count toward the timeout and "Detener" aborts the wait.
    Progress against the time limit is logged once per second.
    Returns (value, elapsed_seconds, stopped).
    """
    stop_event = context.get("stop_event")
    pause_event = context.get("pause_event")
    log = context.get("log")
    show_progress = log is not None and timeout >= PROGRESS_MIN_SECONDS
    start = time.monotonic()
    paused = 0.0
    elapsed = 0.0
    shown = -1
    while True:
        if stop_event is not None and stop_event.is_set():
            return None, elapsed, True
        if pause_event is not None and not pause_event.is_set():
            if show_progress:
                log(progress_bar(elapsed, timeout, paused=True), "progress")
            pause_started = time.monotonic()
            pause_event.wait()
            paused += time.monotonic() - pause_started
            shown = -1
            continue
        value = check()
        elapsed = time.monotonic() - start - paused
        if value:
            return value, elapsed, False
        if elapsed >= timeout:
            return None, elapsed, False
        if show_progress and int(elapsed) != shown:
            shown = int(elapsed)
            log(progress_bar(elapsed, timeout), "progress")
        time.sleep(min(interval, max(0.0, timeout - elapsed)))
