import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:camera/camera.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:web_socket_channel/io.dart';
import 'package:record/record.dart'; // record package
import 'package:flutter_pcm_sound/flutter_pcm_sound.dart';
import 'package:audio_session/audio_session.dart';
import 'package:image/image.dart' as img;
import '../services/api_service.dart';

class GeminiLiveScreen extends StatefulWidget {
  const GeminiLiveScreen({super.key});

  @override
  State<GeminiLiveScreen> createState() => _GeminiLiveScreenState();
}

class _GeminiLiveScreenState extends State<GeminiLiveScreen> {
  CameraController? _cameraController;
  final AudioRecorder _audioRecorder = AudioRecorder();

  WebSocketChannel? _channel;

  bool _isConnecting = true;
  bool _isConnected = false;

  static const int _sampleRate = 16000;

  DateTime _lastFrameTime = DateTime.now();
  final Duration _frameInterval = const Duration(seconds: 1); // 1 FPS
  bool _isProcessingFrame = false;

  StreamSubscription<Uint8List>? _audioSubscription;

  @override
  void initState() {
    super.initState();
    _initialize();
  }

  Future<void> _initialize() async {
    await _requestPermissions();
    await _initAudio();
    await _connectWebSocket();
    await _initCamera();

    if (mounted) {
      setState(() {
        _isConnecting = false;
      });
    }
  }

  Future<void> _requestPermissions() async {
    await [Permission.camera, Permission.microphone].request();
  }

  Future<void> _initCamera() async {
    try {
      final cameras = await availableCameras();
      if (cameras.isEmpty) return;

      final firstCamera = cameras.firstWhere(
        (camera) => camera.lensDirection == CameraLensDirection.front,
        orElse: () => cameras.first,
      );

      _cameraController = CameraController(
        firstCamera,
        ResolutionPreset.medium,
        enableAudio: false,
        imageFormatGroup: ImageFormatGroup.yuv420,
      );

      await _cameraController!.initialize();

      _cameraController!.startImageStream(_processCameraImage);
      if (mounted) setState(() {});
    } catch (e) {
      print("Camera Error: $e");
    }
  }

  Future<void> _initAudio() async {
    try {
      // Init Audio Session
      final session = await AudioSession.instance;
      await session.configure(
        AudioSessionConfiguration(
          avAudioSessionCategory: AVAudioSessionCategory.playAndRecord,
          avAudioSessionCategoryOptions:
              AVAudioSessionCategoryOptions.allowBluetooth |
              AVAudioSessionCategoryOptions.defaultToSpeaker,
          avAudioSessionMode: AVAudioSessionMode.voiceChat,
          avAudioSessionRouteSharingPolicy:
              AVAudioSessionRouteSharingPolicy.defaultPolicy,
          avAudioSessionSetActiveOptions: AVAudioSessionSetActiveOptions.none,
          androidAudioAttributes: const AndroidAudioAttributes(
            contentType: AndroidAudioContentType.speech,
            flags: AndroidAudioFlags.none,
            usage: AndroidAudioUsage.voiceCommunication,
          ),
          androidAudioFocusGainType: AndroidAudioFocusGainType.gain,
          androidWillPauseWhenDucked: true,
        ),
      );

      // Init Mic using record package
      if (await _audioRecorder.hasPermission()) {
        final stream = await _audioRecorder.startStream(
          const RecordConfig(
            encoder: AudioEncoder.pcm16bits,
            sampleRate: _sampleRate,
            numChannels: 1,
          ),
        );

        _audioSubscription = stream.listen(
          (data) {
            _sendAudio(data);
          },
          onError: (e) {
            print("Audio Stream Error: $e");
          },
          onDone: () {
            print("Audio Stream Done (Closed by OS/User)");
          },
        );
      }

      // Init Player
      await FlutterPcmSound.setup(sampleRate: 24000, channelCount: 1);
    } catch (e) {
      print("Audio Error: $e");
    }
  }

  Future<void> _connectWebSocket() async {
    final baseUrl = ApiService.baseUrl;
    String wsUrl = baseUrl.replaceFirst('http', 'ws');
    if (!wsUrl.startsWith('ws')) {
      wsUrl = 'ws://$baseUrl';
    }
    // Remove default port if 8000 is usually stripped in some setups, but here we keep it.
    // CarePal likely runs backend on 8000.
    wsUrl = '$wsUrl/ws/agent/live/';

    print("Connecting to $wsUrl");

    try {
      _channel = IOWebSocketChannel.connect(Uri.parse(wsUrl));

      _channel!.stream.listen(
        (message) {
          _isConnected = true;
          _handleMessage(message);
          if (mounted) setState(() {});
        },
        onError: (error) {
          print("WS Error: $error");
          _isConnected = false;
          if (mounted) setState(() {});
        },
        onDone: () {
          print("WS Done");
          _isConnected = false;
          if (mounted) setState(() {});
        },
      );
    } catch (e) {
      print("WS Connection failed: $e");
    }
  }

  void _handleMessage(dynamic message) {
    if (message is String) {
      try {
        final data = jsonDecode(message);
        final type = data['type'];
        // print("Received WS Message: $type"); // Reduced logging

        if (type == 'audio') {
          final audioBase64 = data['data'];
          if (audioBase64 != null) {
            final audioBytes = base64Decode(audioBase64);
            // Feed to PCM player
            // PcmArrayInt16.fromList takes List<int>
            // audioBytes is Uint8List. We need to interpret it as Int16.
            // We can view the buffer.
            final int16List = audioBytes.buffer.asInt16List();
            FlutterPcmSound.feed(PcmArrayInt16.fromList(int16List));
          }
        } else if (type == 'text') {
          print("Gemini: ${data['content']}");
        }
      } catch (e) {
        print("Error parsing message: $e");
      }
    }
  }

  void _sendAudio(Uint8List data) {
    if (_channel == null) return;

    try {
      // Removed energy calculation and logging to reduce overhead
      if (data.isEmpty) return;

      final b64 = base64Encode(data);
      final payload = jsonEncode({
        "type": "audio",
        "data": b64,
        "mime_type": "audio/pcm;rate=$_sampleRate",
      });
      _channel!.sink.add(payload);
    } catch (e) {
      print("Send Audio Error: $e");
    }
  }

  Future<void> _processCameraImage(CameraImage image) async {
    if (_isProcessingFrame) return;
    if (_channel == null) return;

    final now = DateTime.now();
    if (now.difference(_lastFrameTime) < _frameInterval) return;

    _isProcessingFrame = true;
    _lastFrameTime = now;

    try {
      // Extract necessary data to pass to isolate
      // We cannot pass CameraImage directly
      final planes = image.planes.map((p) => p.bytes).toList();
      final strides = image.planes.map((p) => p.bytesPerRow).toList();
      final width = image.width;
      final height = image.height;

      final request = YuvConvertRequest(
        planes: planes,
        strides: strides,
        width: width,
        height: height,
      );

      final jpeg = await compute(convertYUV420toJPEG, request);

      if (jpeg != null) {
        final b64 = base64Encode(jpeg);
        final payload = jsonEncode({
          "type": "image",
          "data": b64,
          "mime_type": "image/jpeg",
        });
        _channel!.sink.add(payload);
      }
    } catch (e) {
      print("Frame Process Error: $e");
    } finally {
      _isProcessingFrame = false;
    }
  }

  @override
  void dispose() {
    _audioSubscription?.cancel();
    //FlutterPcmSound.stop(); // Removed as it causes error
    _cameraController?.dispose();
    _channel?.sink.close();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        title: const Text("Gemini Live", style: TextStyle(color: Colors.white)),
        backgroundColor: Colors.transparent,
        elevation: 0,
        iconTheme: const IconThemeData(color: Colors.white),
      ),
      extendBodyBehindAppBar: true,
      body: Stack(
        fit: StackFit.expand,
        children: [
          if (_cameraController != null &&
              _cameraController!.value.isInitialized)
            CameraPreview(_cameraController!)
          else
            const Center(child: CircularProgressIndicator(color: Colors.white)),

          Positioned(
            bottom: 40,
            left: 0,
            right: 0,
            child: Center(
              child: Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 24,
                  vertical: 12,
                ),
                decoration: BoxDecoration(
                  color: Colors.black.withOpacity(0.6),
                  borderRadius: BorderRadius.circular(30),
                  border: Border.all(color: Colors.white24),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      _isConnected ? Icons.circle : Icons.error_outline,
                      color: _isConnected
                          ? Colors.greenAccent
                          : Colors.redAccent,
                      size: 16,
                    ),
                    const SizedBox(width: 12),
                    Text(
                      _isConnected ? "Gemini Live Connected" : "Connecting...",
                      style: const TextStyle(color: Colors.white),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class YuvConvertRequest {
  final List<Uint8List> planes;
  final List<int> strides;
  final int width;
  final int height;

  YuvConvertRequest({
    required this.planes,
    required this.strides,
    required this.width,
    required this.height,
  });
}

// Compute Function
Uint8List? convertYUV420toJPEG(YuvConvertRequest req) {
  try {
    final int width = req.width;
    final int height = req.height;

    // Downsample factor (skip pixels to reduce size)
    const int step =
        2; // Process 1 out of every 2 pixels (effectively 1/4 resolution)
    final int newWidth = width ~/ step;
    final int newHeight = height ~/ step;

    // Create Image at reduced resolution
    final image = img.Image(width: newWidth, height: newHeight);

    // Assuming YUV420 structure
    final yPlane = req.planes[0];
    final uPlane = req.planes[1];
    final vPlane = req.planes[2];

    final yStride = req.strides[0];
    final uStride = req.strides[1];
    final vStride = req.strides[2];

    final uvPixelStride = req.planes[1].length > (width * height / 4) ? 2 : 1;

    for (int y = 0; y < newHeight; y++) {
      for (int x = 0; x < newWidth; x++) {
        // Map back to original coordinates
        final int origX = x * step;
        final int origY = y * step;

        final int yIndex = origY * yStride + origX;
        final int index = (origY ~/ 2) * uStride + (origX ~/ 2) * uvPixelStride;

        // Safety check
        if (yIndex >= yPlane.length ||
            index >= uPlane.length ||
            index >= vPlane.length)
          continue;

        final yp = yPlane[yIndex];
        final up = uPlane[index];
        final vp = vPlane[index];

        // Convert to RGB
        int r = (yp + (1.370705 * (vp - 128))).round().clamp(0, 255);
        int g = (yp - (0.337633 * (up - 128)) - (0.698001 * (vp - 128)))
            .round()
            .clamp(0, 255);
        int b = (yp + (1.732446 * (up - 128))).round().clamp(0, 255);

        image.setPixelRgb(x, y, r, g, b);
      }
    }

    // Compress to JPEG
    return img.encodeJpg(
      image,
      quality: 60,
    ); // Reduced quality slightly for speed
  } catch (e) {
    // print("Convert Error: $e");
    return null;
  }
}
