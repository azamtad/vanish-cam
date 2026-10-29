"""Goku-style Instant Transmission: two fingers on the forehead, then teleport.

Everything here is drawn procedurally (no anime frames or sprites):

* ``forehead_pose`` checks MediaPipe hand + face landmarks for index and
  middle finger held straight and together, touching the forehead.
* ``HoldTrigger`` requires the pose to be held for a moment (1 s by default),
  then needs the hand to be lowered before it can fire again.
* ``render_teleport`` draws the vanish (and its reverse for reappearing):
  a short energy flicker, the silhouette squeezing into a thin vertical line,
  a flash, and comic-style vertical speed lines that linger briefly.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import cv2
import numpy as np


TELEPORT_SOUND_PATH = Path(__file__).resolve().parent / "assets" / "teleport.wav"

HOLD_SECONDS = 1.0
# Full length of one teleport animation (out or in), including lingering lines.
TELEPORT_SECONDS = 0.95

# MediaPipe Face Mesh landmark indices.
FACE_TOP = 10          # top of the forehead / hairline centre
FACE_FOREHEAD = 151    # middle of the forehead
FACE_BROW = 9          # between the eyebrows
FACE_NOSE_BRIDGE = 168
FACE_CHIN = 152
FACE_LEFT = 234
FACE_RIGHT = 454

# Energy colours (BGR): pale cyan-white, like the anime's light trace.
GLOW_BGR = np.array((255, 236, 170), dtype=np.float32)
WHITE_BGR = np.array((255, 255, 255), dtype=np.float32)


# --------------------------------------------------------------------------
# Gesture recognition
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Face:
    """Forehead geometry in pixel coordinates."""

    top: np.ndarray       # forehead top (x, y)
    brow: np.ndarray      # between the eyebrows (x, y)
    nose: np.ndarray      # nose bridge (x, y)
    width: float
    height: float

    @property
    def center_x(self) -> float:
        return float(self.brow[0])


def face_from_landmarks(face_landmarks, width: int, height: int) -> Face | None:
    if face_landmarks is None or len(face_landmarks) < 455:
        return None

    def point(index: int) -> np.ndarray:
        landmark = face_landmarks[index]
        return np.array((landmark.x * width, landmark.y * height), dtype=np.float32)

    top, brow, nose = point(FACE_TOP), point(FACE_BROW), point(FACE_NOSE_BRIDGE)
    face_width = float(np.linalg.norm(point(FACE_RIGHT) - point(FACE_LEFT)))
    face_height = float(np.linalg.norm(point(FACE_CHIN) - top))
    if not (np.isfinite(top).all() and np.isfinite(brow).all()) or face_width < 8:
        return None
    return Face(top=top, brow=brow, nose=nose, width=face_width, height=face_height)


def _hand_points(hand, width: int, height: int) -> np.ndarray | None:
    if hand is None or len(hand) != 21:
        return None
    points = np.array([(p.x * width, p.y * height) for p in hand], dtype=np.float32)
    return points if np.isfinite(points).all() else None


def _finger(points: np.ndarray, base: int) -> tuple[float, float, float]:
    """Return (straightness, reach_from_wrist_ratio, length) for one finger."""
    finger = points[base:base + 4]
    length = float(np.linalg.norm(np.diff(finger, axis=0), axis=1).sum())
    if length < 1e-6:
        return 0.0, 0.0, 0.0
    straightness = float(np.linalg.norm(finger[3] - finger[0])) / length
    wrist = points[0]
    tip_reach = float(np.linalg.norm(finger[3] - wrist))
    pip_reach = max(1e-6, float(np.linalg.norm(finger[1] - wrist)))
    return straightness, tip_reach / pip_reach, length


def _distance_to_segment(point: np.ndarray, a: np.ndarray, b: np.ndarray) -> float:
    ab = b - a
    t = float(np.clip(np.dot(point - a, ab) / max(1e-6, float(np.dot(ab, ab))), 0.0, 1.0))
    return float(np.linalg.norm(point - (a + ab * t)))


def two_finger_hand(points: np.ndarray) -> bool:
    """Index + middle straight and side by side, ring + pinky curled."""
    index_straight, index_reach, index_len = _finger(points, 5)
    middle_straight, middle_reach, middle_len = _finger(points, 9)
    if min(index_len, middle_len) < 6:
        return False
    extended = (
        index_straight >= 0.80 and middle_straight >= 0.80
        and index_reach >= 1.12 and middle_reach >= 1.12
    )
    if not extended:
        return False

    reference = min(index_len, middle_len)
    folded = []
    for base in (13, 17):
        straight, reach, _ = _finger(points, base)
        tip_from_knuckle = float(np.linalg.norm(points[base + 3] - points[base]))
        folded.append(
            straight < 0.72 or reach < 1.08 or tip_from_knuckle < reference * 0.62
        )
    if not all(folded):
        return False

    # Fingers together (not a V): tips close compared to finger length.
    tip_gap = float(np.linalg.norm(points[8] - points[12]))
    return tip_gap <= reference * 0.45


def forehead_pose(hands: Sequence, face: Face | None, width: int, height: int) -> bool:
    """True when any hand holds two fingers together against the forehead."""
    if face is None:
        return False
    # The forehead "line" runs from a bit above the hairline down to the brows.
    up = face.top - face.brow
    above = face.top + up * 0.35
    for hand in hands:
        points = _hand_points(hand, width, height)
        if points is None or not two_finger_hand(points):
            continue
        tips = (points[8] + points[12]) * 0.5
        near = _distance_to_segment(tips, above, face.brow) <= face.width * 0.42
        # Fingertips must be above the nose bridge and the hand should not
        # be hanging far below the face (rules out a raised hand in front of
        # the chest that happens to overlap the forehead in 2D).
        above_nose = tips[1] <= face.nose[1] + face.height * 0.05
        wrist_reasonable = points[0][1] <= face.top[1] + face.height * 2.2
        if near and above_nose and wrist_reasonable:
            return True
    return False


@dataclass
class HoldTrigger:
    """Fire after the pose is held continuously; re-arm once it is released."""

    hold_seconds: float = HOLD_SECONDS
    grace_seconds: float = 0.3     # brief tracking drop-outs are forgiven
    rearm_seconds: float = 0.35    # pose must be absent this long to re-arm
    armed: bool = True
    held_since: float | None = None
    last_seen: float | None = None
    absent_since: float | None = None

    def reset(self, armed: bool = True) -> None:
        self.armed = armed
        self.held_since = self.last_seen = self.absent_since = None

    def progress(self, now: float) -> float:
        if not self.armed or self.held_since is None:
            return 0.0
        return float(np.clip((now - self.held_since) / self.hold_seconds, 0.0, 1.0))

    def update(self, pose: bool, now: float) -> bool:
        if pose:
            self.absent_since = None
            if not self.armed:
                return False
            if self.held_since is None:
                self.held_since = now
            self.last_seen = now
            if now - self.held_since >= self.hold_seconds:
                self.reset(armed=False)
                return True
            return False

        if self.held_since is not None and self.last_seen is not None:
            if now - self.last_seen > self.grace_seconds:
                self.held_since = self.last_seen = None
        if not self.armed:
            if self.absent_since is None:
                self.absent_since = now
            if now - self.absent_since >= self.rearm_seconds:
                self.armed = True
                self.absent_since = None
        return False


@dataclass
class FaceMemory:
    """Keep the last face for a moment: a hand on the forehead can hide it."""

    keep_seconds: float = 1.5
    face: Face | None = None
    seen_at: float = -math.inf

    def update(self, face: Face | None, now: float) -> Face | None:
        if face is not None:
            self.face, self.seen_at = face, now
            return face
        if self.face is not None and now - self.seen_at <= self.keep_seconds:
            return self.face
        return None


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------

def _smooth(value: float) -> float:
    value = float(np.clip(value, 0.0, 1.0))
    return value * value * (3.0 - 2.0 * value)


def _ease_in(value: float) -> float:
    value = float(np.clip(value, 0.0, 1.0))
    return value * value * value


def silhouette_box(mask: np.ndarray | None, shape: tuple[int, int]) -> tuple[int, int, int, int]:
    """Bounding box (x, y, w, h) of the person, or a centred default."""
    height, width = shape
    if mask is not None:
        points = cv2.findNonZero((mask > 0.35).astype(np.uint8))
        if points is not None:
            x, y, w, h = cv2.boundingRect(points)
            if w * h > width * height * 0.004:
                return x, y, w, h
    return int(width * 0.35), int(height * 0.12), int(width * 0.30), int(height * 0.88)


@dataclass
class TeleportStyle:
    """Timing of one teleport animation (seconds, for the 'out' direction)."""

    charge_end: float = 0.12      # flicker / energy outline
    squeeze_end: float = 0.40     # body collapses into a vertical line
    flash_end: float = 0.50       # thin bright line, then gone
    lines_end: float = TELEPORT_SECONDS
    line_count: int = 30
    seed: int = 4049


STYLE = TeleportStyle()


def _speed_lines(canvas: np.ndarray, box: tuple[int, int, int, int], strength: float,
                 frame_index: int, style: TeleportStyle = STYLE) -> None:
    """Comic-style vertical speed lines over the silhouette area."""
    if strength <= 0.01:
        return
    height, width = canvas.shape[:2]
    x, y, w, h = box
    cx = x + w * 0.5
    spread = max(w * 0.75, height * 0.10)
    top = max(0, int(y - h * 0.12))
    bottom = min(height, int(y + h * 1.04))
    if bottom <= top:
        return
    # Lines flicker: a new random set every 2 frames, like hand-drawn animation.
    rng = np.random.default_rng(style.seed + frame_index // 2)
    layer = np.zeros((bottom - top, width), dtype=np.float32)
    dark = np.zeros_like(layer)
    span = bottom - top
    for _ in range(style.line_count):
        lx = int(np.clip(cx + rng.normal(0.0, spread * 0.45), 0, width - 1))
        length = int(span * rng.uniform(0.25, 0.95))
        start = int(rng.uniform(0, max(1, span - length)))
        thickness = int(rng.choice((1, 1, 2, 2, 3)))
        target = dark if rng.random() < 0.18 else layer
        cv2.line(target, (lx, start), (lx, start + length), float(rng.uniform(0.55, 1.0)),
                 thickness, cv2.LINE_AA)
    # Fade lines towards their ends for a softer comic look.
    falloff = np.clip(np.sin(np.linspace(0.0, np.pi, span, dtype=np.float32)), 0.0, 1.0)
    falloff = falloff[:, None] ** 0.6
    layer = cv2.GaussianBlur(layer, (0, 0), 0.8) * falloff * strength
    dark = dark * falloff * strength * 0.55
    region = canvas[top:bottom].astype(np.float32)
    region *= (1.0 - dark[:, :, None])
    region += (WHITE_BGR * 0.85 + GLOW_BGR * 0.15 - region) * layer[:, :, None]
    canvas[top:bottom] = np.clip(region, 0, 255).astype(np.uint8)


def _flash_line(canvas: np.ndarray, box: tuple[int, int, int, int], strength: float) -> None:
    if strength <= 0.01:
        return
    height, width = canvas.shape[:2]
    x, y, w, h = box
    cx = int(x + w * 0.5)
    glow = np.zeros((height, width), dtype=np.float32)
    top, bottom = max(0, y - int(h * 0.05)), min(height - 1, y + h)
    cv2.line(glow, (cx, top), (cx, bottom), 1.0, max(2, w // 60), cv2.LINE_AA)
    glow = np.clip(cv2.GaussianBlur(glow, (0, 0), max(3.0, w / 40.0)) * 2.4 + glow, 0, 1)
    glow *= strength
    out = canvas.astype(np.float32)
    out += (GLOW_BGR - out) * glow[:, :, None] * 0.9
    canvas[:] = np.clip(out, 0, 255).astype(np.uint8)


def _composite_person(canvas: np.ndarray, frame: np.ndarray, mask: np.ndarray,
                      box: tuple[int, int, int, int], squeeze: float, whiten: float,
                      outline: float, opacity: float, jitter: float) -> None:
    """Warp the person (squeeze horizontally, stretch a bit vertically) onto canvas."""
    if opacity <= 0.005:
        return
    x, y, w, h = box
    cx = x + w * 0.5 + jitter
    cy = y + h * 0.55
    sx = max(0.015, 1.0 - squeeze)
    sy = 1.0 + 0.10 * squeeze
    matrix = np.float32(((sx, 0.0, cx - sx * (x + w * 0.5)), (0.0, sy, cy - sy * cy)))
    size = (frame.shape[1], frame.shape[0])
    if abs(sx - 1.0) < 1e-3 and abs(sy - 1.0) < 1e-3 and abs(jitter) < 0.5:
        person, alpha = frame, mask
    else:
        person = cv2.warpAffine(frame, matrix, size, flags=cv2.INTER_LINEAR,
                                borderMode=cv2.BORDER_CONSTANT)
        alpha = cv2.warpAffine(mask, matrix, size, flags=cv2.INTER_LINEAR,
                               borderMode=cv2.BORDER_CONSTANT)
    alpha = np.clip(alpha * opacity, 0.0, 1.0)
    colour = person.astype(np.float32)
    if whiten > 0.0:
        colour += (WHITE_BGR * 0.7 + GLOW_BGR * 0.3 - colour) * whiten
    out = canvas.astype(np.float32)
    out = colour * alpha[:, :, None] + out * (1.0 - alpha[:, :, None])
    if outline > 0.0:
        hard = (alpha > 0.4).astype(np.uint8)
        edge = hard - cv2.erode(hard, np.ones((5, 5), np.uint8))
        rim = cv2.GaussianBlur(edge.astype(np.float32), (0, 0), 4.0) * 3.0
        rim = np.clip(rim + edge, 0.0, 1.0) * outline
        out += (GLOW_BGR - out) * rim[:, :, None] * 0.85
    canvas[:] = np.clip(out, 0, 255).astype(np.uint8)


def render_teleport(frame: np.ndarray, background: np.ndarray, mask: np.ndarray | None,
                    age: float, reverse: bool = False,
                    box: tuple[int, int, int, int] | None = None,
                    style: TeleportStyle = STYLE) -> np.ndarray:
    """Render one frame of the teleport.

    ``age`` is seconds since the effect began. ``reverse=True`` plays the
    reappearance: lines first, then the body expands out of a bright line.
    """
    if mask is None:
        mask = np.zeros(frame.shape[:2], dtype=np.float32)
    if box is None:
        box = silhouette_box(mask, frame.shape[:2])
    total = style.lines_end
    # Map reverse playback onto the same timeline.
    t = (total - age) if reverse else age
    t = float(np.clip(t, 0.0, total))
    frame_index = int(age * 30)

    canvas = background.copy()

    # Body: charge (flicker + outline), then squeeze into a line.
    if t < style.flash_end:
        charge = _smooth(t / style.charge_end)
        squeeze_t = (t - style.charge_end) / (style.squeeze_end - style.charge_end)
        squeeze = _ease_in(squeeze_t) if t > style.charge_end else 0.0
        flicker = 0.0
        if t < style.squeeze_end:
            flicker = 0.35 * (1.0 if (frame_index % 3 == 0) else 0.0) * charge
        whiten = min(1.0, 0.25 * charge + 0.85 * squeeze + flicker)
        opacity = 1.0 if t < style.squeeze_end else max(
            0.0, 1.0 - (t - style.squeeze_end) / (style.flash_end - style.squeeze_end) * 3.0)
        jitter = (math.sin(age * 90.0) * box[2] * 0.012) * charge * (1.0 - squeeze)
        _composite_person(canvas, frame, mask, box, squeeze, whiten,
                          outline=charge, opacity=opacity, jitter=jitter)

    # Bright vertical line at the moment of disappearance.
    flash_center = style.squeeze_end + 0.02
    flash = max(0.0, 1.0 - abs(t - flash_center) / 0.10)
    _flash_line(canvas, box, flash)

    # Speed lines: build up during the squeeze, then linger and fade.
    if t < style.charge_end * 0.5:
        lines = 0.0
    elif t < style.squeeze_end:
        lines = _smooth((t - style.charge_end * 0.5) / (style.squeeze_end - style.charge_end * 0.5))
    else:
        lines = 1.0 - _smooth((t - style.squeeze_end) / (style.lines_end - style.squeeze_end))
    _speed_lines(canvas, box, lines, frame_index, style)
    return canvas


# --------------------------------------------------------------------------
# Sound
# --------------------------------------------------------------------------

def synthesize_teleport_sound(path: Path = TELEPORT_SOUND_PATH, rate: int = 44100) -> Path:
    """Write a short original 'zhwip' teleport sound (WAV, 16-bit mono)."""
    import wave

    duration = 0.42
    t = np.linspace(0.0, duration, int(rate * duration), endpoint=False)
    # Rising-then-falling chirp with a fast attack.
    freq = 380.0 + 2600.0 * np.exp(-((t - 0.06) ** 2) / 0.0018)
    phase = 2.0 * np.pi * np.cumsum(freq) / rate
    tone = np.sin(phase) + 0.35 * np.sin(phase * 2.01)
    rng = np.random.default_rng(11)
    noise = rng.standard_normal(t.size)
    # Simple high-pass on the noise for an airy "whoosh".
    noise = np.diff(noise, prepend=0.0)
    envelope = np.minimum(1.0, t / 0.006) * np.exp(-t / 0.10)
    whoosh_env = np.minimum(1.0, t / 0.02) * np.exp(-t / 0.07)
    signal = tone * envelope * 0.65 + noise * whoosh_env * 0.18
    # Tiny "pop" at the end, when the body is gone.
    pop_t = t - 0.15
    pop = np.where(pop_t > 0, np.sin(2 * np.pi * 180 * pop_t) * np.exp(-pop_t / 0.03), 0.0)
    signal += pop * 0.35
    signal /= max(1e-6, float(np.abs(signal).max()))
    pcm = (signal * 0.9 * 32767).astype("<i2")
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(rate)
        output.writeframes(pcm.tobytes())
    return path


if __name__ == "__main__":
    print(f"Wrote {synthesize_teleport_sound()}")
