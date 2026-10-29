"""Tests for the Goku Instant Transmission mode.  Run: python -m unittest test_goku_effect"""

import unittest
from types import SimpleNamespace

import numpy as np

from goku_effect import (
    TELEPORT_SECONDS, FaceMemory, HoldTrigger, face_from_landmarks, forehead_pose,
    render_teleport, silhouette_box, two_finger_hand,
)

W, H = 960, 540


def to_landmarks(points_px):
    return [SimpleNamespace(x=x / W, y=y / H, z=0.0) for x, y in points_px]


def make_hand(tip_center=(480, 120), fingers_together=True, ring_pinky_folded=True,
              index_middle_straight=True):
    """A right hand pointing up, wrist below the fingertips (pixel coords)."""
    tx, ty = tip_center
    wrist = (tx + 10, ty + 200)
    pts = [None] * 21
    pts[0] = wrist
    # thumb: tucked
    for i, p in zip(range(1, 5), [(tx + 40, ty + 170), (tx + 50, ty + 145), (tx + 40, ty + 125), (tx + 25, ty + 120)]):
        pts[i] = p
    gap = 10 if fingers_together else 55
    for base, x in ((5, tx - gap / 2), (9, tx + gap / 2)):
        mcp_y = ty + 110
        if index_middle_straight:
            pts[base:base + 4] = [(x, mcp_y), (x, ty + 70), (x, ty + 35), (x, ty)]
        else:
            pts[base:base + 4] = [(x, mcp_y), (x, ty + 80), (x + 15, ty + 95), (x + 10, ty + 115)]
    for base, x in ((13, tx + 25), (17, tx + 42)):
        mcp_y = ty + 115
        if ring_pinky_folded:
            pts[base:base + 4] = [(x, mcp_y), (x, ty + 90), (x + 8, ty + 110), (x + 5, ty + 128)]
        else:
            pts[base:base + 4] = [(x, mcp_y), (x, ty + 80), (x, ty + 50), (x, ty + 20)]
    return to_landmarks(pts)


def make_face(center=(480, 230), size=200):
    cx, cy = center
    pts = [(cx, cy)] * 478
    pts = list(pts)
    pts[10] = (cx, cy - size * 0.55)    # forehead top
    pts[9] = (cx, cy - size * 0.25)     # brow
    pts[168] = (cx, cy - size * 0.15)   # nose bridge
    pts[152] = (cx, cy + size * 0.55)   # chin
    pts[234] = (cx - size * 0.42, cy)
    pts[454] = (cx + size * 0.42, cy)
    return face_from_landmarks(to_landmarks(pts), W, H)


def as_points(landmarks):
    return np.array([(p.x * W, p.y * H) for p in landmarks], dtype=np.float32)


class GestureTests(unittest.TestCase):
    def test_two_fingers_together_on_forehead(self):
        face = make_face()
        forehead = face.top * 0.5 + face.brow * 0.5
        hand = make_hand(tip_center=tuple(forehead))
        self.assertTrue(two_finger_hand(as_points(hand)))
        self.assertTrue(forehead_pose([hand], face, W, H))

    def test_rejects_v_sign_open_hand_and_fist(self):
        face = make_face()
        tip = tuple(face.top * 0.5 + face.brow * 0.5)
        for kwargs in ({"fingers_together": False}, {"ring_pinky_folded": False},
                       {"index_middle_straight": False}):
            with self.subTest(**kwargs):
                self.assertFalse(forehead_pose([make_hand(tip, **kwargs)], face, W, H))

    def test_rejects_hand_far_from_forehead(self):
        face = make_face()
        self.assertFalse(forehead_pose([make_hand((820, 150))], face, W, H))   # off to the side
        self.assertFalse(forehead_pose([make_hand((480, 330))], face, W, H))   # at the chin
        self.assertFalse(forehead_pose([make_hand((480, 120))], None, W, H))   # no face

    def test_face_memory_survives_short_occlusion(self):
        memory = FaceMemory(keep_seconds=1.0)
        face = make_face()
        self.assertIs(memory.update(face, 0.0), face)
        self.assertIs(memory.update(None, 0.8), face)
        self.assertIsNone(memory.update(None, 1.3))


class HoldTriggerTests(unittest.TestCase):
    def test_fires_after_hold_then_requires_release(self):
        trigger = HoldTrigger(hold_seconds=1.0, grace_seconds=0.3, rearm_seconds=0.35)
        t = 0.0
        fired = []
        while t < 1.2:
            fired.append(trigger.update(True, t))
            t += 0.05
        self.assertEqual(sum(fired), 1)
        # Still holding: must not fire again.
        for _ in range(30):
            t += 0.05
            self.assertFalse(trigger.update(True, t))
        # Lower the hand, then hold again: fires a second time.
        for _ in range(10):
            t += 0.05
            trigger.update(False, t)
        self.assertTrue(trigger.armed)
        second = [trigger.update(True, t + 0.05 * i) for i in range(1, 25)]
        self.assertEqual(sum(second), 1)

    def test_short_dropout_is_forgiven_but_long_break_restarts(self):
        trigger = HoldTrigger(hold_seconds=1.0, grace_seconds=0.3)
        trigger.update(True, 0.0)
        trigger.update(False, 0.5)          # 0.5 s since last seen -> reset
        trigger.update(False, 0.6)
        self.assertIsNone(trigger.held_since)
        trigger.update(True, 1.0)
        trigger.update(False, 1.2)          # brief dropout (0.2 s)
        self.assertFalse(trigger.update(True, 1.5))
        self.assertTrue(trigger.update(True, 2.0))


class RenderTests(unittest.TestCase):
    def setUp(self):
        self.background = np.full((H, W, 3), 90, np.uint8)
        self.frame = self.background.copy()
        self.mask = np.zeros((H, W), np.float32)
        self.mask[100:500, 400:560] = 1.0
        self.frame[100:500, 400:560] = (30, 80, 220)

    def test_start_shows_person_and_end_shows_background(self):
        box = silhouette_box(self.mask, (H, W))
        start = render_teleport(self.frame, self.background, self.mask, 0.0, box=box)
        np.testing.assert_array_equal(start[300, 480], self.frame[300, 480])
        end = render_teleport(self.frame, self.background, self.mask, TELEPORT_SECONDS, box=box)
        np.testing.assert_array_equal(end, self.background)

    def test_reverse_ends_with_person(self):
        box = silhouette_box(self.mask, (H, W))
        end = render_teleport(self.frame, self.background, self.mask, TELEPORT_SECONDS,
                              reverse=True, box=box)
        np.testing.assert_array_equal(end[300, 480], self.frame[300, 480])

    def test_mid_effect_squeezes_person(self):
        box = silhouette_box(self.mask, (H, W))
        mid = render_teleport(self.frame, self.background, self.mask, 0.38, box=box)
        # The left edge of the body should now be background-ish (squeezed away).
        self.assertLess(abs(int(mid[300, 410, 2]) - 90), 60)
        self.assertTrue(np.isfinite(mid).all())


if __name__ == "__main__":
    unittest.main()
