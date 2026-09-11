"""Unit tests for registration-reference matching behaviour."""
from __future__ import annotations

import unittest
from unittest import mock

import numpy as np

from app.detection.face_embedder import best_registered_match


class RegisteredMatchTest(unittest.TestCase):
    def test_best_reference_pose_is_used_instead_of_only_its_average(self):
        live = np.array([1.0, 0.0], dtype=np.float32)
        registrations = [{
            "name": "Known",
            "embedding": [0.7, 0.7],
            "reference_embeddings": [[1.0, 0.0], [0.0, 1.0]],
        }]
        with mock.patch("app.config.FACE_MATCH_THRESHOLD", 0.75):
            name, best, second = best_registered_match(live, registrations)
        self.assertEqual(name, "Known")
        self.assertAlmostEqual(best, 1.0)
        self.assertEqual(second, 0.0)


if __name__ == "__main__":
    unittest.main()
