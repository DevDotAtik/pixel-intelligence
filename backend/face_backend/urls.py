from django.contrib import admin
from django.urls import path, include
from video_analytics.views import HomeView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('detector.urls')),
    path('video/', include('video_analytics.urls', namespace='video_analytics')),
    path('', HomeView.as_view(), name='home'),
]
