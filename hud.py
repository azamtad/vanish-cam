"""On-screen tips for the preview window.

The tips are drawn on a copy of the frame shown in the VanishCam window only.
The virtual camera always receives the clean video. Press H to hide them
(for example when capturing the window in OBS).
"""

from __future__ import annotations

import cv2
import numpy as np

FONT = cv2.FONT_HERSHEY_DUPLEX
TEXT = (245, 245, 245)
DIM = (190, 196, 200)
ACCENT = (255, 214, 92)        # cyan-ish (BGR), matches the teleport glow
PANEL = (24, 22, 20)


def _scale(frame: np.ndarray) -> float:
    return max(0.45, frame.shape[1] / 960.0)


def _panel(canvas: np.ndarray, x1: int, y1: int, x2: int, y2: int, alpha: float = 0.62) -> None:
    height, width = canvas.shape[:2]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(width, x2), min(height, y2)
    if x2 <= x1 or y2 <= y1:
        return
    region = canvas[y1:y2, x1:x2].astype(np.float32)
    region = region * (1.0 - alpha) + np.array(PANEL, np.float32) * alpha
    canvas[y1:y2, x1:x2] = region.astype(np.uint8)


def _centered(canvas: np.ndarray, text: str, y: int, size: float, color, thickness: int) -> None:
    (w, _), _ = cv2.getTextSize(text, FONT, size, thickness)
    x = (canvas.shape[1] - w) // 2
    cv2.putText(canvas, text, (x, y), FONT, size, color, thickness, cv2.LINE_AA)


def draw_hud(frame: np.ndarray, title: str | None, subtitle: str | None = None,
             progress: float | None = None, footer: str | None = None,
             big: bool = False) -> np.ndarray:
    """Return a copy of ``frame`` with tips drawn on it."""
    canvas = frame.copy()
    s = _scale(canvas)
    height, width = canvas.shape[:2]

    if title:
        title_size = (1.15 if big else 0.78) * s
        sub_size = (0.8 if big else 0.58) * s
        (tw, th), _ = cv2.getTextSize(title, FONT, title_size, max(1, int(2 * s)))
        sw = cv2.getTextSize(subtitle, FONT, sub_size, 1)[0][0] if subtitle else 0
        box_w = int(max(tw, sw, 260 * s) + 60 * s)
        box_h = int((th + 30 * s) + (34 * s if subtitle else 0) + (24 * s if progress is not None else 0))
        if big:
            top = (height - box_h) // 2
        else:
            top = int(height - box_h - 52 * s)
        left = (width - box_w) // 2
        _panel(canvas, left, top, left + box_w, top + box_h)
        y = int(top + 18 * s + th)
        _centered(canvas, title, y, title_size, TEXT, max(1, int(2 * s)))
        if subtitle:
            y += int(34 * s)
            _centered(canvas, subtitle, y, sub_size, DIM, 1)
        if progress is not None:
            bar_w = int(box_w - 60 * s)
            bx, by = left + int(30 * s), y + int(14 * s)
            bh = max(4, int(7 * s))
            cv2.rectangle(canvas, (bx, by), (bx + bar_w, by + bh), (70, 70, 70), -1, cv2.LINE_AA)
            filled = int(bar_w * float(np.clip(progress, 0.0, 1.0)))
            if filled > 0:
                cv2.rectangle(canvas, (bx, by), (bx + filled, by + bh), ACCENT, -1, cv2.LINE_AA)

    if footer:
        size = 0.45 * s
        (fw, fh), _ = cv2.getTextSize(footer, FONT, size, 1)
        pad = int(8 * s)
        x = (width - fw) // 2
        y = height - int(14 * s)
        _panel(canvas, x - pad, y - fh - pad, x + fw + pad, y + pad, alpha=0.5)
        cv2.putText(canvas, footer, (x, y), FONT, size, DIM, 1, cv2.LINE_AA)
    return canvas


FOOTER = "SPACE new background  |  M menu  |  H hide tips  |  F fullscreen  |  Q quit"


def tips_for(mode: str, phase: str, calibration_left: int | None,
             hold_progress: float, hold_armed: bool) -> dict | None:
    """Pick the tip for the current state; None means draw nothing (mid-effect)."""
    if phase == "calibrating":
        left = calibration_left if calibration_left is not None else 4
        return {"title": "Step out of the frame",
                "subtitle": f"Capturing the background...  {max(left, 0)}", "big": True}
    if phase in ("vanishing", "naruto_vanishing", "goku_out", "goku_in"):
        return None
    if mode == "goku":
        if hold_progress > 0:
            return {"title": "Instant Transmission...", "progress": hold_progress}
        if phase == "vanished":
            title = "You're gone!  Fingers on forehead to come back"
        else:
            title = "Index + middle finger on your forehead"
        sub = "Hold for a second" if hold_armed else "Lower your hand first"
        return {"title": title, "subtitle": sub}
    if phase == "vanished":
        return {"title": "Press R to reappear"}
    if mode == "naruto":
        return {"title": "Press your palms together", "subtitle": "or press V"}
    return {"title": "Show a V sign to vanish", "subtitle": "or press V"}
