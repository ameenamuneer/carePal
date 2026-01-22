import 'dart:async';
import 'dart:convert';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:web_socket_channel/status.dart' as status;
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// WebSocket Service for AI Agent Real-time Communication
/// Connects to backend/agent/consumers.py AgentConsumer
class WebSocketService {
  final String baseWsUrl;
  final _storage = const FlutterSecureStorage();

  WebSocketChannel? _channel;
  StreamController<Map<String, dynamic>>? _messageController;
  bool _isConnected = false;
  String? _sessionId;

  WebSocketService({required this.baseWsUrl});

  bool get isConnected => _isConnected;
  String? get sessionId => _sessionId;
  Stream<Map<String, dynamic>>? get messages => _messageController?.stream;

  /// Connect to WebSocket with authentication
  Future<void> connect() async {
    if (_isConnected) {
      print('WebSocket already connected');
      return;
    }

    try {
      // Get access token
      final token = await _storage.read(key: 'access_token');
      if (token == null) {
        throw Exception('No access token found');
      }

      // Create WebSocket URL with token
      // Format: ws://localhost:8000/ws/agent/?token=<access_token>
      final wsUrl = '$baseWsUrl/ws/agent/?token=$token';

      print('Connecting to WebSocket: $wsUrl');

      // Create channel
      _channel = WebSocketChannel.connect(Uri.parse(wsUrl));

      // Create message stream controller
      _messageController = StreamController<Map<String, dynamic>>.broadcast();

      // Listen to messages
      _channel!.stream.listen(
        (data) {
          _handleMessage(data);
        },
        onError: (error) {
          print('WebSocket error: $error');
          _handleDisconnect();
        },
        onDone: () {
          print('WebSocket connection closed');
          _handleDisconnect();
        },
      );

      _isConnected = true;
      print('WebSocket connected successfully');
    } catch (e) {
      print('Failed to connect to WebSocket: $e');
      _isConnected = false;
      rethrow;
    }
  }

  /// Handle incoming WebSocket message
  void _handleMessage(dynamic data) {
    try {
      final message = jsonDecode(data as String) as Map<String, dynamic>;

      print('WebSocket message received: ${message['type']}');

      // Handle connection confirmation
      if (message['type'] == 'connection') {
        _sessionId = message['session_id'];
        print('Session ID: $_sessionId');
      }

      // Broadcast message to listeners
      _messageController?.add(message);
    } catch (e) {
      print('Error handling WebSocket message: $e');
    }
  }

  /// Send text message to AI
  Future<void> sendMessage(String text) async {
    if (!_isConnected || _channel == null) {
      throw Exception('WebSocket not connected');
    }

    try {
      final message = {'type': 'text', 'message': text};

      _channel!.sink.add(jsonEncode(message));
      print('Sent message: $text');
    } catch (e) {
      print('Error sending message: $e');
      rethrow;
    }
  }

  /// Send audio data to AI (base64 encoded)
  Future<void> sendAudio(String audioDataBase64) async {
    if (!_isConnected || _channel == null) {
      throw Exception('WebSocket not connected');
    }

    try {
      final message = {'type': 'audio', 'audio': audioDataBase64};

      _channel!.sink.add(jsonEncode(message));
      print('Sent audio data');
    } catch (e) {
      print('Error sending audio: $e');
      rethrow;
    }
  }

  /// Handle disconnection
  void _handleDisconnect() {
    _isConnected = false;
    _sessionId = null;
    _messageController?.add({
      'type': 'disconnected',
      'message': 'WebSocket connection lost',
    });
  }

  /// Disconnect WebSocket
  Future<void> disconnect() async {
    if (!_isConnected) {
      return;
    }

    try {
      await _channel?.sink.close(status.normalClosure);
      _isConnected = false;
      _sessionId = null;
      await _messageController?.close();
      _messageController = null;
      print('WebSocket disconnected');
    } catch (e) {
      print('Error disconnecting WebSocket: $e');
    }
  }

  /// Dispose resources
  void dispose() {
    disconnect();
  }
}

/// Provider for WebSocket Service
class WebSocketProvider {
  static WebSocketService? _instance;

  static WebSocketService getInstance({required String baseWsUrl}) {
    _instance ??= WebSocketService(baseWsUrl: baseWsUrl);
    return _instance!;
  }

  static void disposeInstance() {
    _instance?.dispose();
    _instance = null;
  }
}
