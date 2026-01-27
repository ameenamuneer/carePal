from django.urls import re_path
from . import consumers, live_consumer

websocket_urlpatterns = [
    re_path(r'ws/agent/$', consumers.AgentConsumer.as_asgi()),
    re_path(r'ws/agent/live/$', live_consumer.GeminiLiveConsumer.as_asgi()),
]
