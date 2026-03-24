import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:camera/camera.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:web_socket_channel/io.dart';
import 'package:record/record.dart';
import 'package:flutter_pcm_sound/flutter_pcm_sound.dart';
import 'package:audio_session/audio_session.dart';
import 'package:image/image.dart' as img;
import 'package:provider/provider.dart';
import '../services/api_service.dart';
import '../services/ble_servo_service.dart';

class GeminiLiveScreen extends StatefulWidget {
  const GeminiLiveScreen({Key? key}) : super(key: key);

  @override
  State<GeminiLiveScreen> createState() => _GeminiLiveScreenState();
}

class _GeminiLiveScreenState extends State<GeminiLiveScreen> {
  CameraController? _cameraController;
  final AudioRecorder _audioRecorder = AudioRecorder();
  final BleServoService _bleServoService = BleServoService();

  WebSocketChannel? _channel;
  bool _isConnecting = true;
  bool _isConnected = false;
  bool _isDisposed = false;

  static const int _sampleRate = 16000;
  // 256ms buffer (4096 samples * 2 bytes) = 8192 bytes
  static const int _targetBufferSize = 8192; 
  Uint8List _micBuffer = Uint8List(0);

  DateTime _lastFrameTime = DateTime.now();
  final Duration _frameInterval = const Duration(seconds: 1);
  bool _isProcessingFrame = false;

  StreamSubscription<Uint8List>? _audioSubscription;

  @override
  void initState() {
    super.initState();
    _initialize();
  }

  Future<void> _initialize() async {
    await _requestPermissions();
    // 1. SETUP PCM PLAYER FIRST (Crucial for AEC reference signal)
    await _initAudioSystem(); 
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

  Future<void> _initAudioSystem() async {
    try {
      // Step A: Setup Player (Activates MODE_IN_COMMUNICATION)
      await FlutterPcmSound.setup(sampleRate: 24000, channelCount: 1);

      // Step B: Configure Session (REMOVED 'const' TO FIX BITWISE OR ERROR)
      final session = await AudioSession.instance;
      await session.configure(
        AudioSessionConfiguration(
          avAudioSessionCategory: AVAudioSessionCategory.playAndRecord,
          avAudioSessionCategoryOptions:
              AVAudioSessionCategoryOptions.allowBluetooth |
              AVAudioSessionCategoryOptions.defaultToSpeaker,
          avAudioSessionMode: AVAudioSessionMode.voiceChat,
          androidAudioAttributes: const AndroidAudioAttributes(
            contentType: AndroidAudioContentType.speech,
            usage: AndroidAudioUsage.voiceCommunication,
          ),
          androidAudioFocusGainType: AndroidAudioFocusGainType.gain,
        ),
      );

      // Step C: Start Recorder (AEC is now primed)
      if (await _audioRecorder.hasPermission()) {
        final stream = await _audioRecorder.startStream(
          const RecordConfig(
            encoder: AudioEncoder.pcm16bits,
            sampleRate: _sampleRate,
            numChannels: 1,
            androidConfig: AndroidRecordConfig(
              audioSource: AndroidAudioSource.voiceCommunication,
            ),
          ),
        );

        _audioSubscription = stream.listen((data) {
          if (!_isConnected || _isDisposed) return;
          _handleMicBuffering(data);
        });
      }
    } catch (e) {
      print("Audio System Error: $e");
    }
  }

  void _handleMicBuffering(Uint8List newData) {
    final BytesBuilder builder = BytesBuilder(copy: false);
    builder.add(_micBuffer);
    builder.add(newData);
    _micBuffer = builder.takeBytes();

    while (_micBuffer.length >= _targetBufferSize) {
      final chunkToSend = _micBuffer.sublist(0, _targetBufferSize);
      _micBuffer = _micBuffer.sublist(_targetBufferSize);
      _sendAudio(chunkToSend);
    }
  }

  Future<void> _connectWebSocket() async {
    final baseUrl = ApiService.baseUrl;
    String wsUrl = baseUrl.replaceFirst('http', 'ws');
    if (!wsUrl.startsWith('ws')) wsUrl = 'ws://$baseUrl';
    wsUrl = '$wsUrl/ws/agent/live/';

    final token = await ApiService().getAccessToken();
    if (token != null) wsUrl = '$wsUrl?token=$token';

    try {
      _channel = IOWebSocketChannel.connect(Uri.parse(wsUrl));
      _isConnected = true;
      if (mounted) setState(() {});

      _channel!.stream.listen(
        (message) => _handleMessage(message),
        onError: (_) {
          _isConnected = false;
          if (mounted) setState(() {});
        },
        onDone: () {
          _isConnected = false;
          if (mounted) setState(() {});
        },
      );
    } catch (e) {
      print("WS Connection failed: $e");
    }
  }

  void _handleMessage(dynamic message) {
    if (message is Uint8List) {
      final typeByte = message[0];
      if (typeByte == 0x00) {
        var audioBytes = message.sublist(1);
        if (audioBytes.length % 2 != 0) audioBytes = audioBytes.sublist(0, audioBytes.length - 1);
        final int16List = audioBytes.buffer.asInt16List(audioBytes.offsetInBytes, audioBytes.lengthInBytes ~/ 2);
        FlutterPcmSound.feed(PcmArrayInt16.fromList(int16List));
      } else if (typeByte == 0x03) {
        _interruptAudio();
      } else if (typeByte == 0x02) {
        final data = jsonDecode(utf8.decode(message.sublist(1)));
        if (data['type'] == 'interrupted') _interruptAudio();
        if (data['type'] == 'camera_control') _bleServoService.setDelta(data['pan_delta'].toString());
      }
    }
  }

  void _interruptAudio() {
    // Clear only the AI's playback queue.
    FlutterPcmSound.clear().catchError((e) => print("Clear error: $e"));
  }

  void _sendAudio(Uint8List data) {
    if (_channel == null || !_isConnected || _isDisposed) return;
    final payload = Uint8List(data.length + 1);
    payload[0] = 0x00;
    payload.setRange(1, payload.length, data);
    _channel!.sink.add(payload);
  }

  Future<void> _initCamera() async {
    try {
      final cameras = await availableCameras();
      if (cameras.isEmpty) return;
      final front = cameras.firstWhere((c) => c.lensDirection == CameraLensDirection.front, orElse: () => cameras.first);

      _cameraController = CameraController(front, ResolutionPreset.medium, enableAudio: false, imageFormatGroup: ImageFormatGroup.yuv420);
      await _cameraController!.initialize();
      _cameraController!.startImageStream(_processCameraImage);
      if (mounted) setState(() {});
    } catch (e) {
      print("Camera Error: $e");
    }
  }

  Future<void> _processCameraImage(CameraImage image) async {
    if (_isProcessingFrame || _channel == null || !_isConnected) return;

    final now = DateTime.now();
    if (now.difference(_lastFrameTime) < _frameInterval) return;

    _isProcessingFrame = true;
    _lastFrameTime = now;

    try {
      final request = YuvConvertRequest(
        planes: image.planes.map((p) => p.bytes).toList(),
        strides: image.planes.map((p) => p.bytesPerRow).toList(),
        width: image.width,
        height: image.height,
      );

      final jpeg = await compute(convertYUV420toJPEG, request);

      if (jpeg != null && !_isDisposed) {
        final payload = Uint8List(jpeg.length + 1);
        payload[0] = 0x01;
        payload.setRange(1, payload.length, jpeg);
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
    _isDisposed = true;
    _isConnected = false;
    _audioSubscription?.cancel();
    _audioRecorder.stop();
    FlutterPcmSound.release();
    _cameraController?.dispose();
    _channel?.sink.close(1000);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      body: Stack(
        fit: StackFit.expand,
        children: [
          if (_cameraController != null && _cameraController!.value.isInitialized)
            CameraPreview(_cameraController!)
          else
            const Center(child: CircularProgressIndicator(color: Colors.white)),
          Positioned(
            bottom: 40,
            left: 20,
            right: 20,
            child: Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Colors.black54,
                borderRadius: BorderRadius.circular(20),
                border: Border.all(color: Colors.white10),
              ),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.circle, color: _isConnected ? Colors.greenAccent : Colors.redAccent, size: 12),
                  const SizedBox(width: 10),
                  Text(_isConnected ? "LIVE" : "DISCONNECTED", style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
                ],
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
  YuvConvertRequest({required this.planes, required this.strides, required this.width, required this.height});
}

Uint8List? convertYUV420toJPEG(YuvConvertRequest req) {
  try {
    const int step = 2; 
    final int newWidth = req.width ~/ step;
    final int newHeight = req.height ~/ step;
    final image = img.Image(width: newWidth, height: newHeight);

    final yPlane = req.planes[0];
    final uPlane = req.planes[1];
    final vPlane = req.planes[2];
    final yStride = req.strides[0];
    final uvPixelStride = req.planes[1].length > (req.width * req.height / 4) ? 2 : 1;

    for (int y = 0; y < newHeight; y++) {
      for (int x = 0; x < newWidth; x++) {
        final int origX = x * step;
        final int origY = y * step;
        final int yIndex = origY * yStride + origX;
        final int index = (origY ~/ 2) * req.strides[1] + (origX ~/ 2) * uvPixelStride;

        if (yIndex >= yPlane.length || index >= uPlane.length) continue;

        final yp = yPlane[yIndex];
        final up = uPlane[index];
        final vp = vPlane[index];

        int r = (yp + (1.370705 * (vp - 128))).round().clamp(0, 255);
        int g = (yp - (0.337633 * (up - 128)) - (0.698001 * (vp - 128))).round().clamp(0, 255);
        int b = (yp + (1.732446 * (up - 128))).round().clamp(0, 255);
        image.setPixelRgb(x, y, r, g, b);
      }
    }
    return img.encodeJpg(image, quality: 50);
  } catch (e) {
    return null;
  }
}