package com.example.carepal_app

import android.content.Context
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.media.audiofx.AcousticEchoCanceler
import android.media.audiofx.AutomaticGainControl
import android.media.audiofx.NoiseSuppressor
import android.os.Handler
import android.os.Looper
import io.flutter.plugin.common.BinaryMessenger
import io.flutter.plugin.common.EventChannel
import io.flutter.plugin.common.MethodCall
import io.flutter.plugin.common.MethodChannel

class AecAudioPlugin(
    private val context: Context,
    messenger: BinaryMessenger,
) : MethodChannel.MethodCallHandler, EventChannel.StreamHandler {

    companion object {
        const val SAMPLE_RATE = 16000
        const val READ_SIZE = 4096  // 128 ms chunks; Dart side accumulates to 8192
    }

    private val methodChannel = MethodChannel(messenger, "carepal/aec_recorder")
    private val eventChannel = EventChannel(messenger, "carepal/aec_recorder_stream")

    private var audioRecord: AudioRecord? = null
    private var aec: AcousticEchoCanceler? = null
    private var ns: NoiseSuppressor? = null
    private var agc: AutomaticGainControl? = null
    private var recordingThread: Thread? = null
    @Volatile private var isRecording = false
    private var eventSink: EventChannel.EventSink? = null
    private val mainHandler = Handler(Looper.getMainLooper())

    init {
        methodChannel.setMethodCallHandler(this)
        eventChannel.setStreamHandler(this)
    }

    // ── MethodChannel ─────────────────────────────────────────────────────────

    override fun onMethodCall(call: MethodCall, result: MethodChannel.Result) {
        when (call.method) {
            "start" -> { startRecording(); result.success(null) }
            "stop"  -> { stopRecording();  result.success(null) }
            else    -> result.notImplemented()
        }
    }

    // ── EventChannel ──────────────────────────────────────────────────────────

    override fun onListen(arguments: Any?, events: EventChannel.EventSink?) {
        eventSink = events
    }

    override fun onCancel(arguments: Any?) {
        eventSink = null
    }

    // ── Recording ─────────────────────────────────────────────────────────────

    private fun startRecording() {
        if (isRecording) return

        val minBuf = AudioRecord.getMinBufferSize(
            SAMPLE_RATE,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT,
        )
        if (minBuf == AudioRecord.ERROR || minBuf == AudioRecord.ERROR_BAD_VALUE) {
            mainHandler.post {
                eventSink?.error("INIT_FAILED", "getMinBufferSize failed", null)
            }
            return
        }

        val ar = AudioRecord(
            MediaRecorder.AudioSource.VOICE_COMMUNICATION,
            SAMPLE_RATE,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT,
            maxOf(minBuf * 2, READ_SIZE * 2),
        )

        if (ar.state != AudioRecord.STATE_INITIALIZED) {
            ar.release()
            mainHandler.post {
                eventSink?.error("INIT_FAILED", "AudioRecord not initialized", null)
            }
            return
        }

        val sessionId = ar.audioSessionId

        // Attach hardware AEC — cancels speaker echo from the microphone signal
        if (AcousticEchoCanceler.isAvailable()) {
            aec = AcousticEchoCanceler.create(sessionId)?.apply { enabled = true }
        }

        // Attach hardware noise suppressor
        if (NoiseSuppressor.isAvailable()) {
            ns = NoiseSuppressor.create(sessionId)?.apply { enabled = true }
        }

        // Attach automatic gain control so mic level is consistent
        if (AutomaticGainControl.isAvailable()) {
            agc = AutomaticGainControl.create(sessionId)?.apply { enabled = true }
        }

        audioRecord = ar
        isRecording = true
        ar.startRecording()

        recordingThread = Thread({
            android.os.Process.setThreadPriority(android.os.Process.THREAD_PRIORITY_URGENT_AUDIO)
            val buf = ByteArray(READ_SIZE)
            while (isRecording) {
                val read = ar.read(buf, 0, READ_SIZE)
                if (read > 0) {
                    val chunk = buf.copyOfRange(0, read)
                    mainHandler.post { eventSink?.success(chunk) }
                }
            }
        }, "AecRecordingThread")
        recordingThread!!.start()
    }

    private fun stopRecording() {
        if (!isRecording) return
        isRecording = false
        recordingThread?.join(500)
        recordingThread = null
        audioRecord?.stop()
        audioRecord?.release()
        audioRecord = null
        aec?.release();  aec = null
        ns?.release();   ns  = null
        agc?.release();  agc = null
    }

    fun destroy() {
        stopRecording()
        methodChannel.setMethodCallHandler(null)
    }
}
