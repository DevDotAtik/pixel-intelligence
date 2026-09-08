from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch

from . import views
from app.analytics.counter import CountingSystem
from app.detection.tracker import TrackingManager


class DashboardTests(TestCase):
    def setUp(self):
        with views.STATE_LOCK:
            views.last_detections = []
            views.last_analytics = {}
            views.last_updated = None
            views.recent_tracks.clear()

    def test_dashboard_renders_prototype_and_privacy_message(self):
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'Sentinel Lens')
        self.assertContains(response, 'no identity recognition')

    def test_sidebar_returns_persistent_anonymous_track_data(self):
        views.update_dashboard_state(
            [{'class': 'face', 'confidence': 0.91, 'tracking_id': 7}],
            {'unique_events': 1, 'total_detections': 1},
        )
        response = self.client.get(reverse('video_analytics:sidebar_data'))
        data = response.json()
        self.assertEqual(data['detection_count'], 1)
        self.assertEqual(data['sidebar']['tracks'][0]['id'], 'Track 7')
        self.assertEqual(data['analytics']['unique_events'], 1)

    def test_tracker_and_counter_keep_current_and_event_counts_distinct(self):
        tracker = TrackingManager()
        counter = CountingSystem()
        first_frame = tracker.update([{'class': 'face', 'bbox': [0, 0, 40, 40], 'confidence': 0.8}])
        second_frame = tracker.update([{'class': 'face', 'bbox': [2, 2, 42, 42], 'confidence': 0.9}])
        self.assertEqual(first_frame[0]['tracking_id'], second_frame[0]['tracking_id'])
        counter.update(first_frame)
        counter.update(second_frame)
        summary = counter.get_summary()
        self.assertEqual(summary['current_counts'], {'face': 1})
        self.assertEqual(summary['class_event_counts'], {'face': 1})

    @patch('video_analytics.views.get_camera')
    def test_unavailable_camera_returns_clear_service_error(self, get_camera):
        class UnavailableCamera:
            class Video:
                @staticmethod
                def isOpened():
                    return False
            video = Video()

        get_camera.return_value = UnavailableCamera()
        response = self.client.get(reverse('video_analytics:stream'))
        self.assertEqual(response.status_code, 503)
        self.assertIn('Camera index', response.json()['error'])
