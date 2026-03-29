# Hardware WebSocket Protocol

This document outlines the WebSocket protocol for real-time communication between the CarePal backend and the hardware device (e.g., the camera/pan motor controller).

## Connection

The hardware WebSocket utilizes the exact same authentication mechanism as the existing Agent WebSockets. The hardware must connect to the backend by providing a valid JWT access token in the query string.

**Endpoint:**
`ws://<backend-url>/ws/hardware/?token=<YOUR_JWT_TOKEN>`

*Note: The token must belong to an authenticated user/device account.*

---

## Message Formats

Communication over this WebSocket is done via JSON. Every message must have a `type` field defining its purpose.

### 1. Querying Camera Pan Motor Position (Backend -> Hardware)

The backend can request the current position of the camera pan motor.

**Payload:**
```json
{
    "type": "query_pan_position"
}
```

### 2. Setting Camera Pan Motor Position (Backend -> Hardware)

The backend can instruct the hardware to move the camera pan motor. Movement can be specified as an absolute position or a delta (relative) value from the current position.

**Absolute Position Payload:**
```json
{
    "type": "set_pan_position",
    "mode": "absolute",
    "value": 90
}
```
*(Where `value` is the target angle/step for the motor).*

**Delta Position Payload:**
```json
{
    "type": "set_pan_position",
    "mode": "delta",
    "value": -15
}
```
*(Where `value` is the change applied to the current position).*

### 3. Hardware Response / Status Update (Hardware -> Backend)

Whenever the hardware receives a `query_pan_position` command, or after it completes a `set_pan_position` command, it should reply with its current position. It can also periodically emit its position if needed.

**Payload:**
```json
{
    "type": "pan_position_status",
    "current_position": 90,
    "status": "idle"  // Can be "moving", "idle", "error"
}
```

### 4. Error Responses (Backend <-> Hardware)

If an invalid command or invalid value is sent, the receiving party should reply with an error.

**Payload:**
```json
{
    "type": "error",
    "message": "Invalid pan position value"
}
```

## Backend Control via Django Channels

The backend can programmatically send messages to the hardware device from anywhere in the Django application (e.g., Celery tasks, other consumers, or views) using Django Channels groups. 

When a hardware device connects, it joins a specific group named `hardware_user_<user_id>`.

**Example: Sending a command from Python code**
```python
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

def send_pan_command(user_id, mode, value):
    channel_layer = get_channel_layer()
    group_name = f"hardware_user_{user_id}"
    
    command_payload = {
        "type": "set_pan_position",
        "mode": mode,
        "value": value
    }
    
    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            "type": "device.command",  # Maps to HardwareConsumer.device_command handler
            "payload": command_payload
        }
    )
```

---

## Future Extensibility
This single WebSocket connection schema is designed to be easily extensible. Additional hardware commands (e.g., tilt control, LED control, or sensor queries) can be added by introducing new `type` values in the JSON messages.
