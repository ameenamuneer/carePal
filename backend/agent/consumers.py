import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Conversation, Message
from django.contrib.auth import get_user_model

User = get_user_model()

class AgentConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        if not self.user.is_authenticated:
            await self.close()
            return
            
        self.room_name = f"user_{self.user.id}"
        await self.accept()

    async def disconnect(self, close_code):
        pass

    async def receive(self, text_data):
        data = json.loads(text_data)
        message_content = data.get('message')
        conversation_id = data.get('conversation_id')

        if not message_content:
            return

        # Save User Message
        conversation = await self.get_conversation(conversation_id)
        await self.save_message(conversation, message_content, 'USER')

        # Mock AI Response
        response_content = f"I received: {message_content}. How can I help you further?"
        await self.save_message(conversation, response_content, 'AI')

        # Send back to WebSocket
        await self.send(text_data=json.dumps({
            'message': response_content,
            'sender': 'AI'
        }))

    @database_sync_to_async
    def get_conversation(self, conversation_id):
        if conversation_id:
            return Conversation.objects.get(id=conversation_id)
        return Conversation.objects.create(user=self.user)

    @database_sync_to_async
    def save_message(self, conversation, content, sender):
        return Message.objects.create(conversation=conversation, content=content, sender=sender)
