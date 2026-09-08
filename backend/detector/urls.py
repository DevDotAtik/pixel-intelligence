from django.urls import path
from .views import FaceDetectionView

urlpatterns = [
    path('detect/', FaceDetectionView.as_view(), name='face_detect'),
]