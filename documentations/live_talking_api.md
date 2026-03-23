### How the Live Talking API Works

The system bridges frontend clients (Flutter, Web, embedded) and Google's Gemini Live API using **Django Channels WebSockets**. The entire flow is managed within `live_consumer.py`.

1. **Connection & Context Gathering**: 
   When the client connects via WebSocket, the server authenticates the user using a JWT token (`?token=...`) and fetches the patient's recent vitals (last 7 days) and active medications. This data is injected into the Gemini AI's "system prompt" so it knows exactly who it's talking to and their current health status.
   
2. **Establishing the Gemini Session**: 
   A connection is opened to the Google Gemini Live API (`gemini-2.5-flash-native-audio-preview`). Two concurrent tasks are started:
   - **Sender Loop**: Monitors an input queue and streams data (audio, images, or text) directly to Gemini.
   - **Receiver Loop**: Listens for incoming responses, tool calls, and audio chunks from Gemini.

3. **Backend Voice Activity Detection (VAD) & Streaming**:
   - The frontend continuously streams `0x00` binary audio packets.
   - The backend runs the audio through a **Silero VAD (Voice Activity Detection)** model.
   - If it's silence, the backend drops the packet to save API bandwidth and prevent hallucinated responses.
   - If confident speech is detected, it forwards it to Gemini.

4. **Fast Interrupts (Barge-in)**:
   - If the AI is currently speaking and the backend VAD suddenly detects loud human speech, the server instantly sends a `0x03` Binary Interrupt signal to the frontend.
   - The frontend immediately clears its audio buffer and stops playback.
   - Gemini's native `interrupted` signal acts as an additional fallback.

5. **Asynchronous AI Tool Execution**: 
   Gemini is given tools like `move_camera` and `record_vital_reading`. 
   - When a tool is triggered, it runs as an asynchronous background task (`asyncio.create_task`) so it never blocks the fast audio streams.
   - For `record_vital_reading`, it saves to the Django DB and replies to Gemini.
   - For `move_camera`, it sends a `0x02` JSON control payload to the frontend.

---

### Live Talking WebSocket API Documentation

**Endpoint:** `ws://<your-domain>/ws/agent/live/?token=<jwt_token>`  
**Protocol:** WebSocket Binary (`wb.binaryType = "arraybuffer"`)  
**Format:** Raw Bytes (Prefix Headers)

To minimize latency and overhead, the WebSocket uses a strict Binary Protocol instead of JSON Strings. Every message sent back and forth is an Array of Bytes (`Uint8Array`), where the very **first byte (Index 0)** determines what the rest of the payload contains.

#### 1. Message Types (Headers)

- `0x00`: Audio (Raw PCM 16-bit)
- `0x01`: Image (JPEG Bytes)
- `0x02`: JSON Control Message (UTF-8 Encoded String)
- `0x03`: Fast Interrupt Signal (No Payload)

#### 2. Client to Server Messages (Sending Data to AI)

**A. Sending Audio (Microphone Stream)**
Streams chunks of microphone data to the AI.
- **Prefix:** `0x00`
- **Payload:** Raw PCM 16-bit at 16000Hz.
```javascript
// Example Construction
const payload = new Uint8Array(1 + pcmBytes.length);
payload[0] = 0x00;
payload.set(pcmBytes, 1);
ws.send(payload.buffer);
```

**B. Sending Image (Camera Frames)**
Sends a visual frame to the AI so it can see the patient or medical devices.
- **Prefix:** `0x01`
- **Payload:** Raw JPEG bytes.
```javascript
const payload = new Uint8Array(1 + jpegBytes.length);
payload[0] = 0x01;
payload.set(jpegBytes, 1);
ws.send(payload.buffer);
```

**C. Sending Text Input**
Sends a text prompt manually.
- **Prefix:** `0x02`
- **Payload:** UTF-8 Encoded JSON string `{"type": "text", "data": "Hello CarePAL"}`
```javascript
const jsonString = JSON.stringify({ "type": "text", "data": "Hello CarePAL" });
const jsonBytes = new TextEncoder().encode(jsonString);
const payload = new Uint8Array(1 + jsonBytes.length);
payload[0] = 0x02;
payload.set(jsonBytes, 1);
ws.send(payload.buffer);
```

#### 3. Server to Client Messages (Receiving Data from AI)

The frontend must listen to the `ArrayBuffer` and extract the first byte to handle the routing.

**A. Receiving Audio (AI Voice Response)**
When the AI speaks, you will receive `0x00` prefixed audio chunks.
- **Prefix:** `0x00`
- **Payload:** Raw PCM 16-bit audio (typically 24kHz from Gemini, check implementation). Feed directly into the audio player.

**B. JSON Control Commands**
The backend sends metadata, text transcripts, and hardware commands as JSON.
- **Prefix:** `0x02`
- **Payload:** UTF-8 Encoded JSON string.
```javascript
// Example Payloads:
{ "type": "text", "content": "I am saving your blood pressure reading now." }
{ "type": "camera_control", "pan_delta": -15 }
```

**C. Fast Interrupt Signal**
Triggered instantly when the backend VAD detects user barge-in, or when Gemini signals a turn interrupt.
- **Prefix:** `0x03`
- **Payload:** None (Length is 1 byte).
**Action Required:** The frontend must immediately stop any currently playing AI audio blocks and clear the playback queue.
