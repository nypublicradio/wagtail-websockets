from django.urls import path, re_path

from . import consumers

websocket_urlpatterns = [
    re_path('ws/chat/p/(?P<room_name>.*)/', consumers.PresenceConsumer)
]
