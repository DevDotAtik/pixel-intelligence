"""Regression tests for the defensive face-identity matching.

These verify the exact behaviour that fixes "anyone is labelled as a registered
person": threshold enforcement, ambiguous-margin rejection, consecutive-name
confirmation and the minimum-face gate. The heavy ONNX embedder is stubbed so the
tests stay fast and deterministic.
"""
from __future__ import annotations

import unittest
from unittest import mock

import numpy as np

from app.detection import subject_service as ss


class SubjectServiceIdentityTest(unittest.TestCase):
    def setUp(self) -> None:
        self.patch_confirm = mock.patch.object(ss, "FACE_MATCH_CONFIRM", 2)
        self.patch_refresh = mock.patch.object(ss, "IDENTITY_REFRESH_SECONDS", 0.0)
        self.patch_margin = mock.patch.object(ss, "FACE_MATCH_MARGIN", 0.10)
        self.patch_threshold = mock.patch.object(ss, "FACE_MATCH_THRESHOLD", 0.82)
        self.patch_min = mock.patch.object(ss, "FACE_MATCH_MIN_FACE", 32)
        self.patch_backend = mock.patch.object(ss, "embedder_backend", return_value="onnx")
        self.patch_quality = mock.patch.object(ss, "face_quality", return_value=(True, "ok"))
        for p in (self.patch_confirm, self.patch_refresh, self.patch_margin,
                  self.patch_threshold, self.patch_min, self.patch_backend,
                  self.patch_quality):
            p.start()
        self.addCleanup(mock.patch.stopall)

        self.service = ss.SubjectService()
        self.service._identities.clear()
        self.crop_ok = np.zeros((64, 64, 3), np.uint8)
        # avoid the real (ONNX) embedder in tests
        ss.extract_embedding = lambda crop: np.ones(512, np.float32)

    def _run(self, matches, n_registrations=1):
        """Feed one scripted best_registered_match result per evaluation."""
        calls = {"n": 0}

        def fake_best(embedding, registrations):
            r = matches[min(calls["n"], len(matches) - 1)]
            calls["n"] += 1
            return r["name"], r["best"], r["second"]

        with mock.patch.object(ss, "best_registered_match", fake_best):
            return [
                self.service._resolve_identity(
                    "sk", self.crop_ok, [{"name": "x"} for _ in range(n_registrations)], 0.0
                )
                for _ in range(len(matches))
            ]

    def test_genuine_person_confirmed_after_two_consecutive_wins(self):
        result = self._run([
            {"name": "A", "best": 0.90, "second": 0.30},
            {"name": "A", "best": 0.90, "second": 0.30},
        ])
        self.assertEqual(result, [None, "A"])

    def test_promising_first_match_is_rechecked_without_waiting_for_refresh(self):
        # The second frame must be able to confirm a candidate even when the
        # normal steady-state refresh interval has not elapsed yet.
        with mock.patch.object(ss, "IDENTITY_REFRESH_SECONDS", 999.0):
            result = self._run([
                {"name": "A", "best": 0.90, "second": 0.30},
                {"name": "A", "best": 0.90, "second": 0.30},
            ])
        self.assertEqual(result, [None, "A"])

    def test_flickering_stranger_never_confirmed(self):
        result = self._run([
            {"name": "A", "best": 0.83, "second": 0.40},
            {"name": "B", "best": 0.84, "second": 0.35},
            {"name": "A", "best": 0.83, "second": 0.38},
        ])
        self.assertEqual(result, [None, None, None])

    def test_ambiguous_enrolment_tie_never_confirmed(self):
        result = self._run([
            {"name": "A", "best": 0.90, "second": 0.82},
            {"name": "A", "best": 0.90, "second": 0.82},
            {"name": "A", "best": 0.90, "second": 0.82},
        ], n_registrations=2)
        self.assertEqual(result, [None, None, None])

    def test_below_threshold_never_confirmed(self):
        result = self._run([
            {"name": "A", "best": 0.81, "second": 0.20},
            {"name": "A", "best": 0.81, "second": 0.20},
            {"name": "A", "best": 0.81, "second": 0.20},
        ])
        self.assertEqual(result, [None, None, None])

    def test_tiny_crop_never_identified_high_scores(self):
        crop_tiny = np.zeros((10, 10, 3), np.uint8)
        with mock.patch.object(ss, "face_quality", return_value=(False, "face is smaller than 32px")), \
             mock.patch.object(ss, "best_registered_match", return_value=("A", 0.99, 0.10)):
            self.assertIsNone(
                self.service._resolve_identity("sk2", crop_tiny, [{"name": "A"}], 0.0)
            )

    def test_histogram_fallback_never_attaches_a_name(self):
        with mock.patch.object(ss, "embedder_backend", return_value="histogram"), \
             mock.patch.object(ss, "best_registered_match", return_value=("A", 0.99, 0.10)):
            self.assertIsNone(
                self.service._resolve_identity("sk3", self.crop_ok, [{"name": "A"}], 0.0)
            )


if __name__ == "__main__":
    unittest.main()
