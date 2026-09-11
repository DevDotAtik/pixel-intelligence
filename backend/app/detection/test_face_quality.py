"""Fast unit tests for the face-quality gate used by enrolment and live matching."""
from __future__ import annotations

import unittest

import cv2
import numpy as np

from app.detection.face_embedder import face_quality


class FaceQualityTest(unittest.TestCase):
    def test_dark_crop_is_rejected(self):
        ok, reason = face_quality(np.zeros((120, 120, 3), dtype=np.uint8))
        self.assertFalse(ok)
        self.assertEqual(reason, "face is too dark")

    def test_sharp_well_lit_crop_is_accepted(self):
        image = np.full((120, 120, 3), 128, dtype=np.uint8)
        for x in range(10, 120, 20):
            cv2.line(image, (x, 0), (x, 119), (30, 30, 30), 3)
        ok, reason = face_quality(image)
        self.assertTrue(ok)
        self.assertEqual(reason, "ok")


if __name__ == "__main__":
    unittest.main()
