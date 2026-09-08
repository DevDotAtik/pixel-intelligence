from django.urls import path
from . import views

app_name = 'video_analytics'

urlpatterns = [
    path('', views.VideoStreamView.as_view(), name='stream'),
    path('detect/', views.DetectView.as_view(), name='detect'),
    path('sidebar-data/', views.SidebarDataView.as_view(), name='sidebar_data'),
]
