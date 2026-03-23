# Voice AI Latency & Interrupt Optimizations

This document outlines the current bottlenecks in the `live_consumer.py` implementation and proposes architecture-agnostic techniques to achieve drastically lower latency and perfect voice interruptions (barge-in). All proposed changes focus on keeping complex logic in the backend to support simple, thin clients across platforms (Web, Flutter/Android, Embedded Hardware).

## 1. Perfecting Interrupts (Barge-in) via Backend Signals

**Current State:** 
The backend receives `interrupted` signals from the Gemini API, but it does not tell the client to stop playing audio. If the user interrupts the AI, the frontend continues playing already buffered audio chunks.

**Proposed Solution:**
*   **Gemini-Triggered Interrupt:** When `server_content.interrupted == True` is received from the Gemini API, immediately push an explicit WebSocket signal to the client (e.g., `{"type": "interrupted"}`). 
*   **Fast VAD-Triggered Interrupt:** Do not wait solely for Gemini to process the audio and return an interrupt flag. Use the proposed Backend VAD (see section 2) to instantly blast an `{"type": "interrupted"}` signal to the client the moment confident high-volume human speech is detected while the AI is speaking.
*   **Agnostic Client Handling:** Any connected client (Web, Flutter, Embedded) simply listens for this JSON event and, upon receipt, stops its current audio playback queue and clears its buffers.

## 2. Server-Side Voice Activity Detection (VAD)

**Current State:**
Clients continuously stream raw audio to the backend. The backend forwards everything directly to the Gemini API, including absolute silence, background noise, or network static. This wastes bandwidth between the backend and Google, adds unnecessary processing delays ("2-layer delay"), and can trigger hallucinatory responses from the AI analyzing noise.

**Proposed Solution:**
*   **Do not offload to the client:** The client should remain a dumb pipe that continuously streams microphone audio and receives speaker audio.
*   **Backend VAD Gatekeeper:** Introduce a lightweight VAD library (like Silero VAD or WebRTC VAD ported to Python) into `live_consumer.py`.
*   **Confidence Thresholds:** As the backend receives audio chunks from the client, the VAD analyzes them for speech confidence. 
    *   If the volume/confidence is low (silence), the backend simply drops the packet and does *not* forward it to Gemini.
    *   If confidence is high, the backend forwards the audio to Gemini.
*   **Result:** The connection to Gemini is kept pristine. Only actual human speech is sent, reducing the "2-layer delay" turnaround time because Gemini processes fewer empty packets.

## 3. Asynchronous Tool Execution (Non-Blocking)

**Current State:**
When Gemini calls a tool (e.g., `record_vital_reading`), the backend awaits the database transaction (`await self.save_vital_reading(...)`) before replying to Gemini. During this database write, the Python receiver loop may briefly freeze, inadvertently blocking the incoming audio streams.

**Proposed Solution:**
*   **Fire-and-Forget Tool Dispatch:** When a tool call is received from Gemini, use `asyncio.create_task()` to execute the database or I/O-bound operations concurrently. 
*   **Immediate Reply:** Acknowledge the tool call to Gemini instantly if the operation is guaranteed, or let the async task send the result back to Gemini upon completion without blocking the main event loops.
*   **Result:** The WebSocket audio streams (both sending and receiving) remain lightning fast and uninterrupted by backend database latency.

## 4. Binary WebSockets vs. JSON/Base64 (Optional but Recommended)

**Current State:**
Audio frames are Base64-encoded, wrapped in JSON, and sent over the WebSocket. 

**Proposed Solution:**
*   While keeping the client architecture agnostic, Flutter, Web, and C++ Embedded devices all natively support raw Binary WebSockets.
*   Switching from Base64 JSON strings to raw PCM byte arrays (with a simple 1-byte header to distinguish Audio/Image/Text) would eliminate the 33% metadata overhead and reduce CPU JSON deserialization time on both the client (e.g., lower battery drain on Android) and the Django backend. This shaves crucial milliseconds off the turnaround latency.

---

### Summary of what to implement next:

1. **Implement Server-Side VAD:** Add a VAD gatekeeper in `sender_loop` to filter out silence and forward only confident speech to Gemini.
2. **The Fast Interrupt Fix:** Send `{"type": "interrupted"}` to the client immediately when the VAD detects speech (Fast Interrupt), and also when Gemini signals an interrupt.
3. **Queue Optimizations & Async Tools:** Wrap `save_vital_reading` and other tool calls in `asyncio.create_task` so the backend loops never block.
