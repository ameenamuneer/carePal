### How the Live Talking API Works

The system bridges the frontend client and Google's Gemini Live API using **Django Channels WebSockets**. The entire flow is managed within `live_consumer.py`.

1. **Connection & Context Gathering**: 
   When the client connects via WebSocket, the server authenticates the user and fetches the patient's recent vitals (last 7 days) and active medications from the database. This data is injected into the Gemini AI's "system prompt" so it knows exactly who it's talking to and their current health status.
   
2. **Establishing the Gemini Session**: 
   A connection is opened to the Google Gemini Live API (`gemini-2.5-flash-native-audio-preview-12-2025`). Two concurrent tasks are started:
   - **Sender Loop**: Constantly monitors an input queue and streams data (audio, images, or text) directly to Gemini.
   - **Receiver Loop**: Listens for incoming responses, tool calls, and audio chunks from Gemini.

3. **Duplex Streaming**: 
   - When the user speaks or the camera captures a frame, the frontend sends base64-encoded JSON payloads to the WebSocket. The server instantly forwards this into the `input_queue`.
   - When Gemini generates speech, it sends raw PCM audio bytes to the server, which base64-encodes them and sends them down the WebSocket to the frontend for playback.

4. **AI Tool Execution**: 
   Gemini is given two tools: `move_camera` and `record_vital_reading`. 
   - If the AI decides to record a vital reading (e.g., you show it a thermometer), it triggers the `record_vital_reading` tool. The server receives this, saves the data to the Django database, and replies to the AI that it succeeded.
   - If the AI needs to look around, it triggers `move_camera` with an integer pan delta. The server forwards this exact command to the frontend so your local BLE device can move the camera.

---

### Live Talking WebSocket API Documentation

**Endpoint:** `ws://<your-domain>/ws/agent/live/`  
**Protocol:** WebSocket (WSS recommended for production)  
**Format:** JSON Payloads

#### 1. Client to Server Messages (Sending Data to AI)

All data sent to the server must be formatted as a JSON object containing a `type`, `data` (base64 encoded), and an optional `mime_type`.

**A. Sending Audio (Microphone Stream)**
Streams chunks of microphone data to the AI.
```json
{
  "type": "audio",
  "mime_type": "audio/pcm;rate=16000",
  "data": "UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAf..." // Base64 encoded audio bytes
}
```

**B. Sending Image (Camera Frames)**
Sends a visual frame to the AI so it can see the patient or medical devices.
```json
{
  "type": "image",
  "mime_type": "image/jpeg",
  "data": "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgH..." // Base64 encoded image bytes
}
```

**C. Sending Text Input**
Sends a text prompt instead of an audio stream.
```json
{
  "type": "text",
  "data": "Hello CarePAL, how are you today?"
}
```

#### 2. Server to Client Messages (Receiving Data from AI)

The frontend should listen to the WebSocket connection and handle the following incoming JSON message types.

**A. Receiving Audio (AI Voice Response)**
When the AI speaks, you will receive base64 encoded audio chunks. Decode and play them immediately to achieve a "live" conversation feel.
```json
{
  "type": "audio",
  "data": "UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAf..." // Base64 encoded audio bytes
}
```

**B. Text Transcripts / Responses**
The AI occasionally sends text transcripts of its speech or supplementary text information.
```json
{
  "type": "text",
  "content": "I am saving your blood pressure reading now."
}
```

**C. Camera Control System Commands**
Triggered when the AI decides it needs to adjust its view. The frontend must intercept this and command the hardware camera to pan.
```json
{
  "type": "camera_control",
  "pan_delta": -15  // Degrees to move horizontally (Negative = Right, Positive = Left)
}
```
*Note: The AI determines the `pan_delta` value dynamically based on what it wants to look at.*

**D. Error Messages**
Sent if there's a problem with the Gemini API key, session initialization, or an internal server crash.
```json
{
  "error": "No Google API Key found"
}
```
