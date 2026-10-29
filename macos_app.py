"""Small macOS niceties (all optional; silently skipped without PyObjC).

* Shows "VanishCam" instead of "Python" in the menu bar.
* Uses the VanishCam icon in the Dock.
* Brings the window to the front when it opens.
* Tells whether the user closed a window with the red button, so the app
  can quit and release the camera.
"""

from __future__ import annotations

import platform
from pathlib import Path

_AppKit = None
if platform.system() == "Darwin":
    try:
        import AppKit as _AppKit  # type: ignore[import-not-found]
        from Foundation import NSBundle  # type: ignore[import-not-found]
    except Exception:  # PyObjC not installed
        _AppKit = None


def set_app_name(name: str = "VanishCam") -> None:
    """Must run before the first OpenCV window is created."""
    if _AppKit is None:
        return
    try:
        bundle = NSBundle.mainBundle()
        info = bundle.localizedInfoDictionary() or bundle.infoDictionary()
        if info is not None:
            info["CFBundleName"] = name
    except Exception:
        pass


def bring_to_front(icon: Path | None = None) -> None:
    if _AppKit is None:
        return
    try:
        app = _AppKit.NSApplication.sharedApplication()
        if icon is not None and icon.is_file():
            image = _AppKit.NSImage.alloc().initWithContentsOfFile_(str(icon))
            if image is not None:
                app.setApplicationIconImage_(image)
        app.activateIgnoringOtherApps_(True)
    except Exception:
        pass


class WindowWatcher:
    """Detect that a window was closed with the red close button."""

    def __init__(self, title: str, cv2_module):
        self.title = title
        self.cv2 = cv2_module
        self.seen_open = False

    def _state(self) -> str | None:
        if _AppKit is not None:
            try:
                for window in _AppKit.NSApplication.sharedApplication().windows():
                    if str(window.title()) == self.title:
                        if window.isMiniaturized():
                            return "minimized"
                        return "open" if window.isVisible() else "closed"
                return "closed" if self.seen_open else None
            except Exception:
                pass
        try:
            visible = self.cv2.getWindowProperty(self.title, self.cv2.WND_PROP_VISIBLE)
        except self.cv2.error:
            return "closed" if self.seen_open else None
        if visible >= 1:
            return "open"
        return "closed" if self.seen_open and platform.system() != "Darwin" else None

    def closed(self) -> bool:
        state = self._state()
        if state == "open":
            self.seen_open = True
            return False
        return self.seen_open and state == "closed"


# --------------------------------------------------------------------------
# Camera permission
# --------------------------------------------------------------------------
# OpenCV only *starts* the macOS permission request and immediately reports
# failure, so a fresh app would quit before the "Allow camera?" pop-up can
# appear. These helpers ask macOS directly and wait for the answer.

_STATUS_NAMES = {0: "undetermined", 1: "restricted", 2: "denied", 3: "authorized"}


def _avfoundation():
    if platform.system() != "Darwin":
        return None
    try:
        import AVFoundation  # type: ignore[import-not-found]
        return AVFoundation
    except Exception:
        return None


def camera_permission_status() -> str | None:
    """'authorized' / 'denied' / 'restricted' / 'undetermined', or None if unknown."""
    av = _avfoundation()
    if av is None:
        return None
    try:
        status = av.AVCaptureDevice.authorizationStatusForMediaType_(av.AVMediaTypeVideo)
        return _STATUS_NAMES.get(int(status))
    except Exception:
        return None


def request_camera_permission(pump=None, timeout: float = 300.0) -> bool | None:
    """Show the macOS camera prompt and wait for the click. None if unavailable."""
    import threading
    import time

    av = _avfoundation()
    if av is None:
        return None
    done = threading.Event()
    answer = [False]

    def handler(granted):
        answer[0] = bool(granted)
        done.set()

    try:
        av.AVCaptureDevice.requestAccessForMediaType_completionHandler_(
            av.AVMediaTypeVideo, handler)
    except Exception:
        return None
    try:
        from Foundation import NSDate, NSRunLoop  # type: ignore[import-not-found]
    except Exception:
        NSDate = NSRunLoop = None
    deadline = time.monotonic() + timeout
    while not done.is_set() and time.monotonic() < deadline:
        if pump is not None:
            pump()
        if NSRunLoop is not None:
            NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.05))
        else:
            time.sleep(0.05)
    if not done.is_set():
        return None
    return answer[0] or camera_permission_status() == "authorized"


def open_camera_settings() -> None:
    import subprocess
    try:
        subprocess.Popen(["open", "x-apple.systempreferences:com.apple.preference.security?Privacy_Camera"])
    except OSError:
        pass
