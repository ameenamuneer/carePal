import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)

class HardwareConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for hardware devices (e.g., camera pan motor controller).
    Handles real-time position querying and setting.
    """
    
    async def connect(self):
        self.user = self.scope["user"]
        
        if not self.user.is_authenticated:
            logger.warning("Unauthenticated hardware connection attempt")
            await self.close()
            return
            
        # Group name based on user ID so backend can easily send hardware commands for this user's device
        self.device_group_name = f"hardware_user_{self.user.id}"
        
        # Join device group
        await self.channel_layer.group_add(
            self.device_group_name,
            self.channel_name
        )

        await self.accept()
        logger.info(f"Hardware WebSocket connected for user {self.user.id}")

    async def disconnect(self, close_code):
        if hasattr(self, 'device_group_name'):
            await self.channel_layer.group_discard(
                self.device_group_name,
                self.channel_name
            )
        logger.info(f"Hardware WebSocket disconnected: {close_code}")

    async def receive(self, text_data):
        """
        Handle incoming messages from the hardware device.
        Usually status updates or error responses.
        """
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'pan_position_status':
                # The hardware sent its current position
                current_position = data.get('current_position')
                status = data.get('status')
                logger.debug(f"Hardware pan position updated to {current_position}, status: {status}")
                # Optional: could save to DB or broadcast to other consumers (like an agent/frontend consumer)
                
            elif message_type == 'error':
                logger.error(f"Hardware reported error: {data.get('message')}")
                
            else:
                logger.warning(f"Unknown message type from hardware: {message_type}")
                
        except json.JSONDecodeError:
            logger.error("Invalid JSON from hardware")
            await self.send_json({"type": "error", "message": "Invalid JSON format"})
        except Exception as e:
            logger.error(f"Error receiving hardware message: {e}")

    async def send_json(self, content):
        """Helper to send JSON response"""
        await self.send(text_data=json.dumps(content))

    # --- Group message handlers ---
    # These methods are called when another part of Django uses channel_layer.group_send()

    async def device_command(self, event):
        """
        Send a command to the hardware.
        Called via group_send with type="device.command".
        """
        command_payload = event.get('payload', {})
        await self.send_json(command_payload)
