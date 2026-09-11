from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch
import numpy as np

from . import views
from app.analytics.counter import CountingSystem
from app.detection.tracker import IoUTracker


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
        tracker = IoUTracker()
        counter = CountingSystem()
        first_frame = tracker.update([{'class': 'face', 'bbox': [0, 0, 40, 40], 'confidence': 0.8}])
        second_frame = tracker.update([{'class': 'face', 'bbox': [2, 2, 42, 42], 'confidence': 0.9}])
        self.assertEqual(first_frame[0]['tracking_id'], second_frame[0]['tracking_id'])
        counter.update(first_frame)
        counter.update(second_frame)
        summary = counter.get_summary()
        self.assertEqual(summary['current_counts'], {'face': 1})
        self.assertEqual(summary['class_event_counts'], {'face': 1})

    def test_tracker_keeps_face_id_when_small_model_box_jitters(self):
        tracker = IoUTracker()
        first = tracker.update([{'class': 'face', 'bbox': [100, 100, 160, 160], 'confidence': 0.8}])
        second = tracker.update([{'class': 'face', 'bbox': [103, 101, 163, 162], 'confidence': 0.8}])
        self.assertEqual(first[0]['tracking_id'], second[0]['tracking_id'])

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
        self.assertIn('is unavailable', response.json()['error'])

    @patch('video_analytics.views._camera_source', return_value=0)
    @patch('video_analytics.views.get_camera')
    def test_registration_snapshot_shares_the_project_camera(self, get_camera, _source):
        class AvailableCamera:
            class Video:
                @staticmethod
                def isOpened():
                    return True
            video = Video()

            @staticmethod
            def get_frame(mirror=False):
                return np.full((24, 24, 3), 127, dtype=np.uint8)

        get_camera.return_value = AvailableCamera()
        response = self.client.get(reverse('video_analytics:snapshot'), {'camera': 'CAM-01'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/jpeg')
        self.assertGreater(len(response.content), 20)

    # ------------------------------------------------------------------
    # Camera registry (CCTV RTSP/MJPEG sources resolved by CAM code)
    # ------------------------------------------------------------------
    @patch('video_analytics.views._fetch_camera_registry')
    def test_registered_rtsp_camera_resolves_with_credentials(self, fetch):
        fetch.return_value = [{
            'code': 'CAM-02', 'name': 'Gate', 'zone': 'Crossing',
            'stream_url': 'rtsp://10.0.0.5:554/stream1',
            'username': 'admin', 'password': 's3cret',
        }]
        self.assertEqual(
            views._camera_source('CAM-02'),
            'rtsp://admin:s3cret@10.0.0.5:554/stream1',
        )

    @patch('video_analytics.views._fetch_camera_registry')
    def test_registered_url_is_used_verbatim_when_creds_already_embedded(self, fetch):
        fetch.return_value = [{
            'code': 'CAM-07', 'stream_url': 'rtsp://user:pw@host/stream',
            'username': 'admin', 'password': 'x',
        }]
        self.assertEqual(views._camera_source('CAM-07'), 'rtsp://user:pw@host/stream')

    @patch('video_analytics.views._fetch_camera_registry')
    def test_unknown_camera_returns_not_configured(self, fetch):
        fetch.return_value = [{'code': 'CAM-02', 'stream_url': 'http://cam/video'}]
        response = self.client.get(
            reverse('video_analytics:stream'), {'camera': 'CAM-09'}
        )
        self.assertEqual(response.status_code, 503)
        self.assertIn('not configured', response.json()['error'])

    def test_credentials_never_injected_twice_when_partial(self):
        self.assertEqual(
            views._apply_credentials('rtsp://host:554/a', 'admin', 'pw'),
            'rtsp://admin:pw@host:554/a',
        )
        self.assertEqual(
            views._apply_credentials('rtsp://user:pw@host:554/a', 'admin', 'pw'),
            'rtsp://user:pw@host:554/a',
        )
        self.assertEqual(views._apply_credentials('', 'admin', 'pw'), '')
        self.assertEqual(views._apply_credentials('http://cam/video', 'a', 'b'), 'http://cam/video')
