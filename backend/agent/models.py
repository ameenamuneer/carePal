from django.db import models
from django.conf import settings

class Conversation(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='conversations')
    started_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    title = models.CharField(max_length=200, blank=True)

class Message(models.Model):
    class Sender(models.TextChoices):
        USER = 'USER', 'User'
        AI = 'AI', 'AI'

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.CharField(max_length=10, choices=Sender.choices)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']
