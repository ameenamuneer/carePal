import 'dart:async';
import 'dart:typed_data';
import 'package:flutter/services.dart';

/// Wraps the native Android AecAudioPlugin.
/// Records PCM16 mono 16 kHz audio with hardware AEC, NoiseSuppressor,
/// and AutomaticGainControl attached to the AudioRecord session.
class AecRecorder {
  static const _methods = MethodChannel('carepal/aec_recorder');
  static const _events = EventChannel('carepal/aec_recorder_stream');

  final _controller = StreamController<Uint8List>.broadcast();
  StreamSubscription<dynamic>? _eventSub;
  bool _started = false;

  Stream<Uint8List> get stream => _controller.stream;

  Future<void> start() async {
    if (_started) return;
    _started = true;

    _eventSub = _events.receiveBroadcastStream().listen(
      (data) {
        if (_controller.isClosed) return;
        if (data is Uint8List) {
          _controller.add(data);
        } else if (data is List) {
          _controller.add(Uint8List.fromList(data.cast<int>()));
        }
      },
      onError: (e) {
        if (!_controller.isClosed) _controller.addError(e);
      },
    );

    await _methods.invokeMethod<void>('start');
  }

  Future<void> stop() async {
    if (!_started) return;
    _started = false;
    await _methods.invokeMethod<void>('stop');
    await _eventSub?.cancel();
    _eventSub = null;
  }

  void dispose() {
    stop();
    _controller.close();
  }
}
