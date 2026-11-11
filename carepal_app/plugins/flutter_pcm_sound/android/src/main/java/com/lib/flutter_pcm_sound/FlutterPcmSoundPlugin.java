package com.lib.flutter_pcm_sound;

import android.os.Build;
import android.media.AudioFormat;
import android.media.AudioManager;
import android.media.AudioTrack;
import android.media.AudioAttributes;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;

import androidx.annotation.NonNull;

import java.util.Map;
import java.util.HashMap;
import java.util.List;
import java.util.ArrayList;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.TimeUnit;
import java.io.StringWriter;
import java.io.PrintWriter;
import java.nio.ByteBuffer;

import io.flutter.embedding.engine.plugins.FlutterPlugin;
import io.flutter.plugin.common.BinaryMessenger;
import io.flutter.plugin.common.MethodCall;
import io.flutter.plugin.common.MethodChannel;

/**
 * FlutterPcmSoundPlugin implements a "one pedal" PCM sound playback mechanism.
 * Playback starts automatically when samples are fed and stops when no more
 * samples are available.
 */
public class FlutterPcmSoundPlugin implements
        FlutterPlugin,
        MethodChannel.MethodCallHandler {
    private static final String CHANNEL_NAME = "flutter_pcm_sound/methods";

    // ── Jitter buffer ────────────────────────────────────────────────────────
    // Network audio arrives in bursts (phone ↔ ngrok jitter of 100–500 ms was
    // measured). Starting playback on the first chunk with only the minimal
    // AudioTrack buffer turned every delivery gap into an underrun: choppy,
    // "robotic" audio until the next burst caught up. Playback now (re)starts
    // only once mPrebufferMs of audio is queued, or after waiting that long, so
    // a gap shorter than the buffer is inaudible and a longer one becomes a
    // clean pause. The target adapts: an underrun mid-reply raises it by
    // PREBUFFER_STEP_MS (up to MAX); CLEAN_REPLIES_TO_DECAY replies without one
    // lower it again (down to MIN), so a good connection keeps the delay small.
    private static final int PREBUFFER_MIN_MS = 100;
    private static final int PREBUFFER_MAX_MS = 400;
    private static final int PREBUFFER_STEP_MS = 100;
    private static final int CLEAN_REPLIES_TO_DECAY = 3;
    // Audio arriving this soon after the queue ran dry means the reply was still
    // going (an underrun); later than this, the previous reply had ended.
    private static final long UNDERRUN_GAP_MS = 1000;
    // Samples are queued and written to the AudioTrack in pieces of this length.
    private static final int WRITE_CHUNK_MS = 20;

    private MethodChannel mMethodChannel;
    private Handler mainThreadHandler = new Handler(Looper.getMainLooper());
    private Thread playbackThread;
    private volatile boolean mShouldCleanup = false;

    private AudioTrack mAudioTrack;
    private int mSampleRate;
    private int mNumChannels;
    private int mMinBufferSize;
    private boolean mDidSetup = false;
    private android.content.Context mContext;

    private long mFeedThreshold = 8000;
    private long mTotalFeeds = 0;
    private long mLastLowBufferFeed = 0;
    private long mLastZeroFeed = 0;

    // Thread-safe queue for storing audio samples
    private final LinkedBlockingQueue<ByteBuffer> mSamples = new LinkedBlockingQueue<>();
    // Bytes currently queued (kept as a running total; guarded by mSamples).
    private long mQueuedBytes = 0;
    // Set by clear(): the playback thread also drops audio already in the AudioTrack.
    private volatile boolean mFlushRequested = false;

    // Adaptive jitter-buffer state (playback thread only).
    private int mPrebufferMs = PREBUFFER_MIN_MS;
    private int mCleanReplies = 0;
    private boolean mUnderrunThisReply = false;

    // Log level enum (kept for potential future use)
    private enum LogLevel {
        NONE,
        ERROR,
        STANDARD,
        VERBOSE
    }

    private LogLevel mLogLevel = LogLevel.VERBOSE;

    @Override
    public void onAttachedToEngine(@NonNull FlutterPluginBinding binding) {
        mContext = binding.getApplicationContext();
        BinaryMessenger messenger = binding.getBinaryMessenger();
        mMethodChannel = new MethodChannel(messenger, CHANNEL_NAME);
        mMethodChannel.setMethodCallHandler(this);
    }

    @Override
    public void onDetachedFromEngine(@NonNull FlutterPluginBinding binding) {
        mMethodChannel.setMethodCallHandler(null);
        cleanup();
    }

    @Override
    @SuppressWarnings("deprecation") // Needed for compatibility with Android < 23
    public void onMethodCall(@NonNull MethodCall call, @NonNull MethodChannel.Result result) {
        try {
            switch (call.method) {
                case "setLogLevel": {
                    result.success(true);
                    break;
                }
                case "setup": {
                    int sampleRate = call.argument("sample_rate");
                    mSampleRate = sampleRate;
                    mNumChannels = call.argument("num_channels");

                    // Cleanup existing resources if any
                    if (mAudioTrack != null) {
                        cleanup();
                    }

                    if (mContext != null) {
                        AudioManager am = (AudioManager) mContext
                                .getSystemService(android.content.Context.AUDIO_SERVICE);
                        if (am != null) {
                            am.setMode(AudioManager.MODE_IN_COMMUNICATION);

                            if (Build.VERSION.SDK_INT >= 31) {
                                // Android 12+: setSpeakerphoneOn is deprecated.
                                // Use the new setCommunicationDevice API instead.
                                android.media.AudioDeviceInfo speakerDevice = null;
                                java.util.List<android.media.AudioDeviceInfo> devices = am
                                        .getAvailableCommunicationDevices();
                                for (android.media.AudioDeviceInfo device : devices) {
                                    if (device.getType() == android.media.AudioDeviceInfo.TYPE_BUILTIN_SPEAKER) {
                                        speakerDevice = device;
                                        break;
                                    }
                                }
                                if (speakerDevice != null) {
                                    boolean ok = am.setCommunicationDevice(speakerDevice);
                                    android.util.Log.d("FlutterPcmSound", "setCommunicationDevice(SPEAKER): " + ok);
                                } else {
                                    android.util.Log.w("FlutterPcmSound",
                                            "BUILTIN_SPEAKER not found in communication devices");
                                }
                            } else {
                                // Android 10 (API 29) and below:
                                // setSpeakerphoneOn requires active audio focus to take effect.
                                // Request focus first, then route.
                                if (Build.VERSION.SDK_INT >= 26) {
                                    android.media.AudioFocusRequest focusReq = new android.media.AudioFocusRequest.Builder(
                                            AudioManager.AUDIOFOCUS_GAIN)
                                            .setAudioAttributes(new AudioAttributes.Builder()
                                                    .setUsage(AudioAttributes.USAGE_VOICE_COMMUNICATION)
                                                    .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                                                    .build())
                                            .build();
                                    am.requestAudioFocus(focusReq);
                                } else {
                                    am.requestAudioFocus(null, AudioManager.STREAM_VOICE_CALL,
                                            AudioManager.AUDIOFOCUS_GAIN);
                                }
                                am.setSpeakerphoneOn(true);
                                android.util.Log.d("FlutterPcmSound",
                                        "setSpeakerphoneOn(true) isSpeakerphoneOn=" + am.isSpeakerphoneOn());
                            }
                        }
                    }

                    int channelConfig = (mNumChannels == 2) ? AudioFormat.CHANNEL_OUT_STEREO
                            : AudioFormat.CHANNEL_OUT_MONO;

                    mMinBufferSize = AudioTrack.getMinBufferSize(
                            sampleRate, channelConfig, AudioFormat.ENCODING_PCM_16BIT);

                    if (mMinBufferSize == AudioTrack.ERROR || mMinBufferSize == AudioTrack.ERROR_BAD_VALUE) {
                        result.error("AudioTrackError", "Invalid buffer size.", null);
                        return;
                    }

                    if (Build.VERSION.SDK_INT >= 23) { // Android 6 (Marshmallow) and above
                        mAudioTrack = new AudioTrack.Builder()
                                .setAudioAttributes(new AudioAttributes.Builder()
                                        .setUsage(AudioAttributes.USAGE_VOICE_COMMUNICATION)
                                        .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                                        .build())
                                .setAudioFormat(new AudioFormat.Builder()
                                        .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                                        .setSampleRate(sampleRate)
                                        .setChannelMask(channelConfig)
                                        .build())
                                .setBufferSizeInBytes(mMinBufferSize)
                                .setTransferMode(AudioTrack.MODE_STREAM)
                                .build();
                    } else {
                        mAudioTrack = new AudioTrack(
                                AudioManager.STREAM_VOICE_CALL,
                                sampleRate,
                                channelConfig,
                                AudioFormat.ENCODING_PCM_16BIT,
                                mMinBufferSize,
                                AudioTrack.MODE_STREAM);
                    }

                    if (mAudioTrack.getState() != AudioTrack.STATE_INITIALIZED) {
                        result.error("AudioTrackError", "AudioTrack initialization failed.", null);
                        mAudioTrack.release();
                        mAudioTrack = null;
                        return;
                    }

                    // reset
                    synchronized (mSamples) {
                        mSamples.clear();
                        mQueuedBytes = 0;
                    }
                    mFlushRequested = false;
                    mShouldCleanup = false;

                    // start playback thread
                    playbackThread = new Thread(this::playbackThreadLoop, "PCMPlaybackThread");
                    playbackThread.setPriority(Thread.MAX_PRIORITY);
                    playbackThread.start();

                    mDidSetup = true;

                    result.success(true);
                    break;
                }
                case "feed": {

                    // check setup (to match iOS behavior)
                    if (mDidSetup == false) {
                        result.error("Setup", "must call setup first", null);
                        return;
                    }

                    byte[] buffer = call.argument("buffer");

                    // Split into WRITE_CHUNK_MS pieces (whole frames)
                    int frameBytes = 2 * mNumChannels;
                    int chunkBytes = Math.max(frameBytes,
                            (mSampleRate * WRITE_CHUNK_MS / 1000) * frameBytes);
                    List<ByteBuffer> chunks = split(buffer, chunkBytes);

                    // Push samples and wake the playback thread
                    synchronized (mSamples) {
                        for (ByteBuffer chunk : chunks) {
                            mSamples.add(chunk);
                        }
                        mQueuedBytes += buffer.length;
                        mTotalFeeds += 1;
                        mSamples.notifyAll();
                    }

                    result.success(true);
                    break;
                }
                case "clear": {
                    // Flush the sample queue without releasing the AudioTrack or
                    // re-requesting audio focus. Safe to call from interrupt handler.
                    synchronized (mSamples) {
                        mSamples.clear();
                        mQueuedBytes = 0;
                        // Also drop what is already inside the AudioTrack, or
                        // the interrupted speech keeps playing for a moment.
                        mFlushRequested = true;
                        mSamples.notifyAll();
                    }
                    result.success(true);
                    break;
                }
                case "setFeedThreshold": {
                    long feedThreshold = ((Number) call.argument("feed_threshold")).longValue();

                    synchronized (mSamples) {
                        mFeedThreshold = feedThreshold;
                    }

                    result.success(true);
                    break;
                }
                case "release": {
                    cleanup();
                    result.success(true);
                    break;
                }
                default:
                    result.notImplemented();
                    break;
            }

        } catch (Exception e) {
            StringWriter sw = new StringWriter();
            PrintWriter pw = new PrintWriter(sw);
            e.printStackTrace(pw);
            String stackTrace = sw.toString();
            result.error("androidException", e.toString(), stackTrace);
            return;
        }
    }

    /**
     * Cleans up resources by stopping the playback thread and releasing AudioTrack.
     */
    private void cleanup() {
        // stop playback thread
        if (playbackThread != null) {
            mShouldCleanup = true;
            playbackThread.interrupt();
            try {
                playbackThread.join();
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
            playbackThread = null;
            mDidSetup = false;
        }
    }

    /**
     * Invokes the 'OnFeedSamples' callback with the number of remaining frames.
     */
    private void invokeFeedCallback(long remainingFrames) {
        Map<String, Object> response = new HashMap<>();
        response.put("remaining_frames", remainingFrames);
        mMethodChannel.invokeMethod("OnFeedSamples", response);
    }

    /**
     * The main loop of the playback thread: an adaptive jitter buffer in front
     * of the AudioTrack (see PREBUFFER_* above).
     */
    private void playbackThreadLoop() {
        android.os.Process.setThreadPriority(android.os.Process.THREAD_PRIORITY_AUDIO);

        mAudioTrack.play();

        final long bytesPerMs = (long) mSampleRate * 2 * mNumChannels / 1000;
        boolean buffering = true;   // waiting to (re)start playback
        long drainedAt = 0;         // when the queue last ran dry mid-playback (0 = idle)

        while (!mShouldCleanup) {
            if (mFlushRequested) {
                // Interrupt (clear): discard audio already handed to the AudioTrack.
                mFlushRequested = false;
                mAudioTrack.pause();
                mAudioTrack.flush();
                mAudioTrack.play();
                buffering = true;
                drainedAt = 0;
                mUnderrunThisReply = false;  // an interrupted reply says nothing about the network
            }

            if (buffering) {
                long queued;
                synchronized (mSamples) {
                    queued = mQueuedBytes;
                    if (queued == 0 && !mFlushRequested && !mShouldCleanup) {
                        try {
                            // Idle: sleep until fed. Mid-reply: wake to notice the reply ended.
                            mSamples.wait(drainedAt > 0 ? 50 : 1000);
                        } catch (InterruptedException e) {
                            Thread.currentThread().interrupt();
                        }
                        queued = mQueuedBytes;
                    }
                }
                long now = SystemClock.elapsedRealtime();
                if (queued == 0) {
                    if (drainedAt > 0 && now - drainedAt > UNDERRUN_GAP_MS) {
                        onReplyEnded();
                        drainedAt = 0;
                    }
                    continue;
                }
                if (drainedAt > 0) {
                    // Audio ran out mid-reply and has resumed: the buffer was too small.
                    onUnderrun();
                    drainedAt = 0;
                }
                // Prebuffer: until mPrebufferMs is queued, or for at most that long.
                long targetBytes = mPrebufferMs * bytesPerMs;
                long deadline = now + mPrebufferMs;
                synchronized (mSamples) {
                    while (!mShouldCleanup && !mFlushRequested && mQueuedBytes < targetBytes) {
                        long left = deadline - SystemClock.elapsedRealtime();
                        if (left <= 0) break;
                        try {
                            mSamples.wait(Math.min(left, 20));
                        } catch (InterruptedException e) {
                            Thread.currentThread().interrupt();
                            break;
                        }
                    }
                }
                buffering = false;
                continue;
            }

            ByteBuffer data = mSamples.poll();
            if (data == null) {
                // Ran dry: buffer up again before resuming.
                buffering = true;
                drainedAt = SystemClock.elapsedRealtime();
                continue;
            }

            long remainingFrames;
            long totalFeeds;
            long feedThreshold;

            // grab shared data
            synchronized (mSamples) {
                mQueuedBytes = Math.max(0, mQueuedBytes - data.remaining());
                remainingFrames = mQueuedBytes / (2 * mNumChannels);
                totalFeeds = mTotalFeeds;
                feedThreshold = mFeedThreshold;
            }

            // write
            mAudioTrack.write(data, data.remaining(), AudioTrack.WRITE_BLOCKING);

            // check for events
            boolean isLowBufferEvent = (remainingFrames <= feedThreshold) && (mLastLowBufferFeed != totalFeeds);
            boolean isZeroCrossingEvent = (remainingFrames == 0) && (mLastZeroFeed != totalFeeds);

            // send events
            if (isLowBufferEvent || isZeroCrossingEvent) {
                if (isLowBufferEvent) {
                    mLastLowBufferFeed = totalFeeds;
                }
                if (isZeroCrossingEvent) {
                    mLastZeroFeed = totalFeeds;
                }
                final long frames = remainingFrames;
                mainThreadHandler.post(() -> invokeFeedCallback(frames));
            }
        }

        mAudioTrack.stop();
        mAudioTrack.flush();
        mAudioTrack.release();
        mAudioTrack = null;
    }

    private void onUnderrun() {
        mUnderrunThisReply = true;
        mCleanReplies = 0;
        if (mPrebufferMs < PREBUFFER_MAX_MS) {
            mPrebufferMs = Math.min(PREBUFFER_MAX_MS, mPrebufferMs + PREBUFFER_STEP_MS);
        }
        android.util.Log.d("FlutterPcmSound", "underrun → prebuffer " + mPrebufferMs + " ms");
    }

    private void onReplyEnded() {
        if (mUnderrunThisReply) {
            mUnderrunThisReply = false;
            return;
        }
        mCleanReplies += 1;
        if (mCleanReplies >= CLEAN_REPLIES_TO_DECAY && mPrebufferMs > PREBUFFER_MIN_MS) {
            mPrebufferMs = Math.max(PREBUFFER_MIN_MS, mPrebufferMs - PREBUFFER_STEP_MS);
            mCleanReplies = 0;
            android.util.Log.d("FlutterPcmSound", "clean replies → prebuffer " + mPrebufferMs + " ms");
        }
    }

    private List<ByteBuffer> split(byte[] buffer, int maxSize) {
        List<ByteBuffer> chunks = new ArrayList<>();
        int offset = 0;
        while (offset < buffer.length) {
            int length = Math.min(buffer.length - offset, maxSize);
            ByteBuffer b = ByteBuffer.wrap(buffer, offset, length);
            chunks.add(b);
            offset += length;
        }
        return chunks;
    }
}
