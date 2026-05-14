import 'dart:async';
import 'dart:convert';
import 'dart:math';
import 'dart:typed_data';
import 'dart:ui' show ImageFilter;
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/scheduler.dart';
import 'package:camera/camera.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:web_socket_channel/io.dart';
import 'package:flutter_pcm_sound/flutter_pcm_sound.dart';
import 'package:image/image.dart' as img;
import 'package:wakelock_plus/wakelock_plus.dart';
import '../services/api_service.dart';
import '../services/ble_servo_service.dart';
import '../services/aec_recorder.dart';

class GeminiLiveScreen extends StatefulWidget {
  const GeminiLiveScreen({Key? key}) : super(key: key);

  @override
  State<GeminiLiveScreen> createState() => _GeminiLiveScreenState();
}

class _GeminiLiveScreenState extends State<GeminiLiveScreen>
    with SingleTickerProviderStateMixin {
  // --- WebSocket ---
  WebSocketChannel? _channel;
  bool _isConnected = false;
  bool _isDisposed = false;

  // --- Audio ---
  final AecRecorder _aecRecorder = AecRecorder();
  StreamSubscription<Uint8List>? _audioSubscription;
  static const int _targetBufferSize = 8192;
  Uint8List _micBuffer = Uint8List(0);
  bool _micOn = true;
  Timer? _speakingTimer;

  // --- Camera ---
  CameraController? _cameraController;
  final BleServoService _bleServoService = BleServoService();
  DateTime _lastFrameTime = DateTime.now();
  final Duration _frameInterval = const Duration(seconds: 1);
  bool _isProcessingFrame = false;
  bool _camVisible = false;

  // --- Animation ---
  late Ticker _ticker;
  Duration _elapsed = Duration.zero;
  double _breathT = 0;
  double _wavePhase = 0;
  double _colorT = 0;
  double _targetColor = 0;
  double _rmsSmooth = 0;
  double _currentRms = 0;

  // --- UI state ---
  bool _isSpeaking = false;
  String _statusText = 'awaiting connection';
  String _tickerText = '';
  bool _tickerIsAi = false;

  @override
  void initState() {
    super.initState();
    WakelockPlus.enable();
    _ticker = createTicker(_onTick)..start();
    _initialize();
  }

  void _onTick(Duration elapsed) {
    if (!mounted || _isDisposed) return;
    _elapsed = elapsed;
    _rmsSmooth += (_currentRms - _rmsSmooth) * 0.19;
    final amp = (_rmsSmooth * 5.8 + 0.06).clamp(0.0, 1.0);
    _colorT += (_targetColor - _colorT) * 0.035;
    _breathT += 0.014;
    _wavePhase += 0.038 + amp * 0.09;
    setState(() {});
  }

  Future<void> _initialize() async {
    await _requestPermissions();
    await _initAudioSystem();
    await _connectWebSocket();
    await _initCamera();
  }

  Future<void> _requestPermissions() async {
    await [Permission.camera, Permission.microphone].request();
  }

  Future<void> _initAudioSystem() async {
    try {
      // FlutterPcmSound.setup sets MODE_IN_COMMUNICATION and USAGE_VOICE_COMMUNICATION
      // on Android, which is the prerequisite for hardware AEC to function.
      await FlutterPcmSound.setup(sampleRate: 24000, channelCount: 1);

      // When the playback buffer fully drains the AI has finished speaking.
      // A 500 ms debounce absorbs brief inter-packet gaps in streamed responses.
      FlutterPcmSound.setFeedCallback((remainingFrames) {
        if (remainingFrames == 0 && !_isDisposed) {
          _speakingTimer?.cancel();
          _speakingTimer = Timer(const Duration(milliseconds: 500), () {
            _setSpeaking(false);
          });
        }
      });

      // AecRecorder creates AudioRecord with VOICE_COMMUNICATION source and
      // explicitly attaches AcousticEchoCanceler + NoiseSuppressor + AGC
      // to the AudioRecord session ID before recording starts.
      await _aecRecorder.start();
      _audioSubscription = _aecRecorder.stream.listen((data) {
        if (_isDisposed) return;
        _handleMicData(data);
      });
    } catch (e) {
      debugPrint('Audio init error: $e');
    }
  }

  static const double _micGain = 2.5;

  void _handleMicData(Uint8List data) {
    final len = data.length ~/ 2;
    if (len == 0) return;

    // Compute RMS from raw (pre-gain) samples so orb reflects true room level.
    // Build gain-boosted buffer for sending in the same pass.
    double sum = 0;
    final boosted = Uint8List(len * 2);
    for (int i = 0; i < len; i++) {
      int s = data[i * 2] | (data[i * 2 + 1] << 8);
      if (s >= 0x8000) s -= 0x10000; // to signed
      final f = s / 32768.0;
      sum += f * f;
      // Apply gain and clamp to PCM16 range
      final boostedS = (s * _micGain).round().clamp(-32768, 32767);
      final u = boostedS < 0 ? boostedS + 0x10000 : boostedS;
      boosted[i * 2]     = u & 0xFF;
      boosted[i * 2 + 1] = (u >> 8) & 0xFF;
    }
    _currentRms = sqrt(sum / len);

    if (!_micOn || !_isConnected) return;

    final builder = BytesBuilder(copy: false);
    builder.add(_micBuffer);
    builder.add(boosted);
    _micBuffer = builder.takeBytes();

    while (_micBuffer.length >= _targetBufferSize) {
      final chunk = _micBuffer.sublist(0, _targetBufferSize);
      _micBuffer = _micBuffer.sublist(_targetBufferSize);
      _sendAudio(chunk);
    }
  }

  void _sendAudio(Uint8List data) {
    if (_channel == null || !_isConnected || _isDisposed) return;
    final payload = Uint8List(data.length + 1);
    payload[0] = 0x00;
    payload.setRange(1, payload.length, data);
    _channel!.sink.add(payload);
  }

  Future<void> _connectWebSocket() async {
    final baseUrl = ApiService.baseUrl;
    String wsUrl = baseUrl.replaceFirst('https://', 'wss://').replaceFirst('http://', 'ws://');
    if (!wsUrl.startsWith('ws')) wsUrl = 'ws://$wsUrl';
    wsUrl = '$wsUrl/ws/agent/live/';

    final token = await ApiService().getAccessToken();
    if (token != null) wsUrl = '$wsUrl?token=$token';

    try {
      _channel = IOWebSocketChannel.connect(Uri.parse(wsUrl));
      _isConnected = true;
      if (mounted) setState(() { _statusText = 'listening'; });

      _channel!.stream.listen(
        _handleMessage,
        onError: (_) {
          _isConnected = false;
          if (mounted) setState(() { _statusText = 'disconnected'; });
        },
        onDone: () {
          _isConnected = false;
          if (mounted) setState(() { _statusText = 'disconnected'; });
        },
      );
    } catch (e) {
      debugPrint('WS connect error: $e');
    }
  }

  void _handleMessage(dynamic message) {
    if (message is! Uint8List) return;
    final typeByte = message[0];
    if (typeByte == 0x00) {
      // Copy to guarantee 2-byte alignment before viewing as Int16List
      final raw = message.sublist(1);
      final aligned = Uint8List.fromList(
          raw.length % 2 == 0 ? raw : raw.sublist(0, raw.length - 1));
      final int16List = aligned.buffer.asInt16List();
      FlutterPcmSound.feed(PcmArrayInt16.fromList(int16List));
      _speakingTimer?.cancel(); // new audio arriving — cancel any pending drain debounce
      _setSpeaking(true);
    } else if (typeByte == 0x03) {
      _interruptAudio();
    } else if (typeByte == 0x02) {
      final data = jsonDecode(utf8.decode(message.sublist(1)));
      if (data['type'] == 'interrupted') _interruptAudio();
      if (data['type'] == 'camera_control') {
        _bleServoService.setDelta(data['pan_delta'].toString());
      }
      if (data['type'] == 'text') {
        if (mounted) setState(() {
          _tickerText = data['content'] ?? '';
          _tickerIsAi = true;
        });
        _setSpeaking(true);
        _rescheduleSpeakingStop();
      }
    }
  }

  // Fallback timer used only for text-only responses that carry no audio.
  // Audio responses are stopped by the PCM buffer-drain callback instead.
  void _rescheduleSpeakingStop() {
    _speakingTimer?.cancel();
    _speakingTimer = Timer(const Duration(seconds: 5), () {
      _setSpeaking(false);
    });
  }

  void _interruptAudio() {
    _speakingTimer?.cancel();
    FlutterPcmSound.clear().catchError((e) => debugPrint('Clear error: $e'));
    _setSpeaking(false);
  }

  void _setSpeaking(bool v) {
    if (!mounted) return;
    setState(() {
      _isSpeaking = v;
      _targetColor = v ? 1.0 : 0.0;
      _statusText = v ? 'responding' : 'listening';
    });
  }

  Future<void> _initCamera() async {
    try {
      final cameras = await availableCameras();
      if (cameras.isEmpty) return;
      final front = cameras.firstWhere(
        (c) => c.lensDirection == CameraLensDirection.front,
        orElse: () => cameras.first,
      );
      _cameraController = CameraController(
        front, ResolutionPreset.medium,
        enableAudio: false,
        imageFormatGroup: ImageFormatGroup.yuv420,
      );
      await _cameraController!.initialize();
      _cameraController!.startImageStream(_processCameraFrame);
      if (mounted) setState(() {});
    } catch (e) {
      debugPrint('Camera init error: $e');
    }
  }

  Future<void> _processCameraFrame(CameraImage image) async {
    if (_isProcessingFrame || !_isConnected || _isDisposed) return;
    final now = DateTime.now();
    if (now.difference(_lastFrameTime) < _frameInterval) return;
    _isProcessingFrame = true;
    _lastFrameTime = now;
    try {
      final req = YuvConvertRequest(
        planes: image.planes.map((p) => p.bytes).toList(),
        strides: image.planes.map((p) => p.bytesPerRow).toList(),
        width: image.width,
        height: image.height,
      );
      final jpeg = await compute(convertYUV420toJPEG, req);
      if (jpeg != null && !_isDisposed && _channel != null) {
        final payload = Uint8List(jpeg.length + 1);
        payload[0] = 0x01;
        payload.setRange(1, payload.length, jpeg);
        _channel!.sink.add(payload);
      }
    } catch (e) {
      debugPrint('Frame error: $e');
    } finally {
      _isProcessingFrame = false;
    }
  }

  void _toggleMic() => setState(() {
    _micOn = !_micOn;
    if (!_micOn) _currentRms = 0;
  });

  void _toggleCam() => setState(() { _camVisible = !_camVisible; });

  @override
  void dispose() {
    WakelockPlus.disable();
    _speakingTimer?.cancel();
    _isDisposed = true;
    _isConnected = false;
    _ticker.dispose();
    _audioSubscription?.cancel();
    _aecRecorder.dispose();
    FlutterPcmSound.release();
    _cameraController?.dispose();
    _channel?.sink.close(1000);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final size = MediaQuery.of(context).size;
    final amp = (_rmsSmooth * 5.8 + 0.06).clamp(0.0, 1.0);
    final elapsedMs = _elapsed.inMilliseconds.toDouble();
    final orbSize = min(size.width * 0.52, size.height * 0.52);

    return Scaffold(
      body: Stack(
        fit: StackFit.expand,
        children: [
          // Animated background
          CustomPaint(
            painter: _BackgroundPainter(colorT: _colorT, elapsedMs: elapsedMs),
          ),

          // Connection dot — top-left
          Positioned(
            top: 48,
            left: 18,
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 450),
              width: 8,
              height: 8,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: _isConnected
                    ? const Color(0xFF32C86E)
                    : const Color(0xFFA0BED7).withOpacity(0.5),
                boxShadow: _isConnected
                    ? [BoxShadow(
                        color: const Color(0xFF32C86E).withOpacity(0.55),
                        blurRadius: 7,
                      )]
                    : null,
              ),
            ),
          ),

          // Orb + status text — centered
          Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                SizedBox(
                  width: orbSize,
                  height: orbSize,
                  child: CustomPaint(
                    painter: _OrbPainter(
                      amp: amp,
                      colorT: _colorT,
                      wavePhase: _wavePhase,
                      breathT: _breathT,
                    ),
                  ),
                ),
                const SizedBox(height: 20),
                Text(
                  _statusText.toUpperCase(),
                  style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w300,
                    letterSpacing: 4.0,
                    color: _isSpeaking
                        ? const Color(0xFF1EA55A).withOpacity(0.8)
                        : const Color(0xFF3C78BE).withOpacity(0.65),
                  ),
                ),
              ],
            ),
          ),

          // Ticker text
          if (_tickerText.isNotEmpty)
            Positioned(
              bottom: size.height * 0.12,
              left: 0,
              right: 0,
              child: Center(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 580),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 20),
                    child: Text(
                      _tickerText,
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w300,
                        letterSpacing: 1.0,
                        height: 1.75,
                        color: _tickerIsAi
                            ? const Color(0xFF199B55).withOpacity(0.8)
                            : const Color(0xFF326EAF).withOpacity(0.65),
                      ),
                    ),
                  ),
                ),
              ),
            ),

          // Camera preview — top-right
          if (_cameraController != null &&
              _cameraController!.value.isInitialized)
            Positioned(
              top: 18,
              right: 18,
              child: AnimatedOpacity(
                opacity: _camVisible ? 1.0 : 0.0,
                duration: const Duration(milliseconds: 350),
                child: AnimatedScale(
                  scale: _camVisible ? 1.0 : 0.88,
                  duration: const Duration(milliseconds: 350),
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(14),
                    child: SizedBox(
                      width: 148,
                      height: 110,
                      child: CameraPreview(_cameraController!),
                    ),
                  ),
                ),
              ),
            ),

          // Control buttons — bottom
          Positioned(
            bottom: size.height * 0.04,
            left: 0,
            right: 0,
            child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                _ControlButton(
                  icon: '🎙',
                  isOn: _micOn,
                  onTap: _toggleMic,
                ),
                const SizedBox(width: 12),
                _ControlButton(
                  icon: '📷',
                  isOn: _camVisible,
                  onTap: _toggleCam,
                ),
                const SizedBox(width: 12),
                _ControlButton(
                  icon: '✕',
                  isDanger: true,
                  onTap: () {
                    _channel?.sink.close(1000);
                    Navigator.of(context).pop();
                  },
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

// ── Background Painter ───────────────────────────────────────────────────────

class _BackgroundPainter extends CustomPainter {
  final double colorT;
  final double elapsedMs;

  const _BackgroundPainter({required this.colorT, required this.elapsedMs});

  Color _lerp(Color a, Color b) => Color.lerp(a, b, colorT)!;

  @override
  void paint(Canvas canvas, Size size) {
    final s = sin(elapsedMs * 0.0004);
    final c2 = cos(elapsedMs * 0.0003);
    final ox = s * size.width * 0.06;
    final oy = c2 * size.height * 0.06;

    // Blue palette: [210,235,248], [188,222,240], [162,205,228]
    // Green palette: [205,245,220], [175,230,200], [145,215,175]
    final c0 = _lerp(const Color(0xFFD2EBF8), const Color(0xFFCDF5DC));
    final c1 = _lerp(const Color(0xFFBCDEF0), const Color(0xFFAFE6C8));
    final c2c = _lerp(const Color(0xFFA2CDE4), const Color(0xFF91D7AF));

    final cx = size.width * 0.5 + ox;
    final cy = size.height * 0.45 + oy;

    final gradient = RadialGradient(
      center: Alignment(
        (cx - size.width / 2) / (size.width / 2),
        (cy - size.height / 2) / (size.height / 2),
      ),
      radius: 1.4,
      colors: [c0, c1, c2c],
    );
    final paint = Paint()
      ..shader = gradient.createShader(
          Rect.fromLTWH(0, 0, size.width, size.height));
    canvas.drawRect(Rect.fromLTWH(0, 0, size.width, size.height), paint);
  }

  @override
  bool shouldRepaint(_BackgroundPainter old) => true;
}

// ── Orb Painter ──────────────────────────────────────────────────────────────

class _OrbPainter extends CustomPainter {
  final double amp;
  final double colorT;
  final double wavePhase;
  final double breathT;

  static const int _nPts = 96;

  const _OrbPainter({
    required this.amp,
    required this.colorT,
    required this.wavePhase,
    required this.breathT,
  });

  // Blue palette
  static const _blueSpec = Color(0xFFEBF8FF);
  static const _blueBase = Color(0xFFAAD7F5);
  static const _blueMid  = Color(0xFF73B4E6);
  static const _blueDark = Color(0xFF468CD2);
  // Green palette
  static const _greenSpec = Color(0xFFE1FCEE);
  static const _greenBase = Color(0xFFA5EBC3);
  static const _greenMid  = Color(0xFF64C896);
  static const _greenDark = Color(0xFF37A06C);

  Color _l(Color a, Color b) => Color.lerp(a, b, colorT)!;

  Path _buildPath(double cx, double cy, double r) {
    final path = Path();
    for (int i = 0; i <= _nPts; i++) {
      final a = (i / _nPts) * pi * 2;
      final w1 = amp * 0.19 * sin(3 * a + wavePhase);
      final w2 = amp * 0.10 * sin(5 * a - wavePhase * 1.4);
      final w3 = amp * 0.055 * sin(7 * a + wavePhase * 0.8);
      final w4 = amp * 0.03 * sin(11 * a - wavePhase * 0.5);
      final br = 0.035 * sin(breathT);
      final dr = r * (1 + br + w1 + w2 + w3 + w4);
      final x = cx + cos(a) * dr;
      final y = cy + sin(a) * dr;
      i == 0 ? path.moveTo(x, y) : path.lineTo(x, y);
    }
    path.close();
    return path;
  }

  @override
  void paint(Canvas canvas, Size size) {
    final cx = size.width / 2;
    final cy = size.height / 2;
    final r = min(size.width, size.height) * 0.38;

    final spec = _l(_blueSpec, _greenSpec);
    final base = _l(_blueBase, _greenBase);
    final mid  = _l(_blueMid,  _greenMid);
    final dark = _l(_blueDark, _greenDark);

    final blobPath = _buildPath(cx, cy, r);

    // 1. Outer glow
    final ogR = r * 1.6;
    canvas.drawCircle(
      Offset(cx, cy),
      ogR,
      Paint()
        ..shader = RadialGradient(
          colors: [
            mid.withOpacity(0.16 + amp * 0.14),
            base.withOpacity(0.06 + amp * 0.05),
            base.withOpacity(0),
          ],
          stops: const [0.0, 0.5, 1.0],
        ).createShader(Rect.fromCircle(center: Offset(cx, cy), radius: ogR)),
    );

    // 2. Blob body
    canvas.drawPath(
      blobPath,
      Paint()
        ..shader = RadialGradient(
          center: const Alignment(-0.27, -0.27),
          focal: const Alignment(0.10, 0.11),
          focalRadius: 0.04,
          radius: 1.0,
          colors: [
            spec.withOpacity(0.88),
            base.withOpacity(0.72),
            mid.withOpacity(0.52),
            dark.withOpacity(0.32),
            dark.withOpacity(0.18),
          ],
          stops: const [0.0, 0.18, 0.5, 0.82, 1.0],
        ).createShader(Rect.fromCircle(center: Offset(cx, cy), radius: r * 1.05)),
    );

    // 3. Inner caustic volume
    canvas.save();
    canvas.clipPath(blobPath);
    canvas.drawRect(
      Rect.fromLTWH(0, 0, size.width, size.height),
      Paint()
        ..shader = RadialGradient(
          colors: [
            spec.withOpacity(0.55),
            base.withOpacity(0.18),
            mid.withOpacity(0.09),
            dark.withOpacity(0.25),
          ],
          stops: const [0.0, 0.25, 0.6, 1.0],
        ).createShader(Rect.fromCircle(
            center: Offset(cx - r * 0.15, cy - r * 0.2), radius: r * 0.9)),
    );
    canvas.restore();

    // 4. Refraction shimmer bands
    canvas.save();
    canvas.clipPath(_buildPath(cx, cy, r));
    for (int i = 0; i < 3; i++) {
      final ang = -pi * 0.35 + i * 0.28 + amp * 0.15 * sin(breathT + i);
      final bx = cx + cos(ang) * r * 0.55;
      final by = cy + sin(ang) * r * 0.55;
      canvas.drawRect(
        Rect.fromLTWH(0, 0, size.width, size.height),
        Paint()
          ..shader = RadialGradient(
            colors: [spec.withOpacity(0.12), spec.withOpacity(0)],
          ).createShader(Rect.fromCircle(
              center: Offset(bx, by), radius: r * 0.32)),
      );
    }
    canvas.restore();

    // 5. Main specular
    canvas.save();
    canvas.clipPath(_buildPath(cx, cy, r));
    canvas.drawRect(
      Rect.fromLTWH(0, 0, size.width, size.height),
      Paint()
        ..shader = RadialGradient(
          colors: [
            Colors.white.withOpacity(0.92),
            Colors.white.withOpacity(0.38),
            Colors.white.withOpacity(0.09),
            Colors.white.withOpacity(0),
          ],
          stops: const [0.0, 0.28, 0.6, 1.0],
        ).createShader(Rect.fromCircle(
            center: Offset(cx - r * 0.37, cy - r * 0.41), radius: r * 0.44)),
    );
    canvas.restore();

    // 6. Secondary specular
    canvas.save();
    canvas.clipPath(_buildPath(cx, cy, r));
    canvas.drawRect(
      Rect.fromLTWH(0, 0, size.width, size.height),
      Paint()
        ..shader = RadialGradient(
          colors: [
            Colors.white.withOpacity(0.45),
            Colors.white.withOpacity(0),
          ],
        ).createShader(Rect.fromCircle(
            center: Offset(cx + r * 0.3, cy + r * 0.28), radius: r * 0.19)),
    );
    canvas.restore();

    // 7. Rim
    canvas.drawPath(
      _buildPath(cx, cy, r),
      Paint()
        ..style = PaintingStyle.stroke
        ..color = spec.withOpacity(0.72 + amp * 0.22)
        ..strokeWidth = 1.8,
    );

    // 8. Audio ripple rings
    if (amp > 0.035) {
      for (int i = 0; i < 3; i++) {
        final ph = ((wavePhase * 0.055 + i / 3) % 1.0).abs();
        final rr = r * (1.02 + ph * 0.62);
        final ra = (1 - ph) * amp * 0.5;
        canvas.drawCircle(
          Offset(cx, cy),
          rr,
          Paint()
            ..style = PaintingStyle.stroke
            ..color = mid.withOpacity(ra)
            ..strokeWidth = 1.1,
        );
      }
    }
  }

  @override
  bool shouldRepaint(_OrbPainter old) => true;
}

// ── Control Button ───────────────────────────────────────────────────────────

class _ControlButton extends StatelessWidget {
  final String icon;
  final bool isOn;
  final bool isDanger;
  final VoidCallback onTap;

  const _ControlButton({
    required this.icon,
    required this.onTap,
    this.isOn = false,
    this.isDanger = false,
  });

  @override
  Widget build(BuildContext context) {
    final Color borderColor;
    final Color bgColor;

    if (isDanger) {
      borderColor = const Color(0xFFDC5050).withOpacity(0.35);
      bgColor = Colors.white.withOpacity(0.28);
    } else if (isOn) {
      borderColor = const Color(0xFF3CBE6E).withOpacity(0.55);
      bgColor = const Color(0xFFB4F5D2).withOpacity(0.22);
    } else {
      borderColor = const Color(0xFF64AAE6).withOpacity(0.3);
      bgColor = Colors.white.withOpacity(0.28);
    }

    return GestureDetector(
      onTap: onTap,
      child: ClipOval(
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: 14, sigmaY: 14),
          child: Container(
            width: 48,
            height: 48,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: bgColor,
              border: Border.all(color: borderColor),
              boxShadow: [
                BoxShadow(
                  color: const Color(0xFF5096DC).withOpacity(0.12),
                  blurRadius: 14,
                  offset: const Offset(0, 4),
                ),
              ],
            ),
            child: Center(
              child: Text(icon, style: const TextStyle(fontSize: 17)),
            ),
          ),
        ),
      ),
    );
  }
}

// ── YUV → JPEG helpers (unchanged) ──────────────────────────────────────────

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
    final uvPixelStride =
        req.planes[1].length > (req.width * req.height / 4) ? 2 : 1;

    for (int y = 0; y < newHeight; y++) {
      for (int x = 0; x < newWidth; x++) {
        final int origX = x * step;
        final int origY = y * step;
        final int yIndex = origY * yStride + origX;
        final int index =
            (origY ~/ 2) * req.strides[1] + (origX ~/ 2) * uvPixelStride;

        if (yIndex >= yPlane.length || index >= uPlane.length) continue;

        final yp = yPlane[yIndex];
        final up = uPlane[index];
        final vp = vPlane[index];

        final r = (yp + (1.370705 * (vp - 128))).round().clamp(0, 255);
        final g = (yp - (0.337633 * (up - 128)) - (0.698001 * (vp - 128)))
            .round()
            .clamp(0, 255);
        final b = (yp + (1.732446 * (up - 128))).round().clamp(0, 255);
        image.setPixelRgb(x, y, r, g, b);
      }
    }
    return img.encodeJpg(image, quality: 50);
  } catch (e) {
    return null;
  }
}
