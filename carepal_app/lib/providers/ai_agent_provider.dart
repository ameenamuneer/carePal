import 'package:flutter/foundation.dart';
import '../services/ai_agent_service.dart';
import '../services/websocket_service.dart';

class AIAgentProvider with ChangeNotifier {
  final AIAgentService _service = AIAgentService();
  late WebSocketService _webSocketService;

  // Initialize with base URL from environment or constant
  // Assuming a default for now, ideally passed in or retrieved from config
  final String _baseWsUrl = 'ws://127.0.0.1:8000';

  int? _sessionId; // Changed to int to match new service
  List<ChatMessage> _messages = [];
  bool _isLoading = false;
  bool _isListening = false;
  String? _error;

  AIAgentProvider() {
    _webSocketService = WebSocketProvider.getInstance(baseWsUrl: _baseWsUrl);
    // Listen to incoming messages
    _webSocketService.messages?.listen((data) {
      _handleIncomingMessage(data);
    });
  }

  int? get sessionId => _sessionId;
  List<ChatMessage> get messages => _messages;
  bool get isLoading => _isLoading;
  bool get isListening => _isListening;
  String? get error => _error;

  // Handle incoming WebSocket messages
  void _handleIncomingMessage(Map<String, dynamic> data) {
    if (data['type'] == 'message') {
      final text = data['message'] ?? '';
      _messages.add(
        ChatMessage(text: text, isUser: false, timestamp: DateTime.now()),
      );
      notifyListeners();
    } else if (data['type'] == 'connection') {
      // Optionally store session ID from WS connection if needed
      // _sessionId = int.tryParse(data['session_id']);
    }
  }

  // Start conversation (Connect WebSocket + Optional Create REST Session)
  Future<void> startConversation(int patientId) async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      // 1. Connect WebSocket first (Server might create session auto)
      await _webSocketService.connect();

      // 2. Optionally, create an explicit session via REST if needed for tracking
      // But typically WS handles it. Let's assume we just use WS for now.
      // Or if we want to track it in backend explicitly before WS:
      // final session = await _service.createSession(patientId: patientId);
      // _sessionId = session['id'];

      _messages = [];
      _isLoading = false;
      notifyListeners();
    } catch (e) {
      _error = e.toString();
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<void> sendMessage(String message) async {
    if (!_webSocketService.isConnected) {
      _error = "Not connected";
      notifyListeners();
      return;
    }

    // Add user message locally
    _messages.add(
      ChatMessage(text: message, isUser: true, timestamp: DateTime.now()),
    );
    notifyListeners();

    try {
      await _webSocketService.sendMessage(message);
    } catch (e) {
      _error = e.toString();
      notifyListeners();
    }
  }

  Future<void> loadHistory(int sessionId) async {
    _isLoading = true;
    notifyListeners();

    try {
      final msgs = await _service.getSessionMessages(sessionId);
      _messages = msgs.map((msg) {
        final content = msg['content'] ?? '';
        final role = msg['role'] ?? 'user';
        final timestampStr =
            msg['created_at'] ?? DateTime.now().toIso8601String();

        return ChatMessage(
          text: content,
          isUser:
              role ==
              'user', // backend likely uses 'user' vs 'agent'/'assistant'
          timestamp: DateTime.parse(timestampStr),
        );
      }).toList();

      _sessionId = sessionId;
      _isLoading = false;
      notifyListeners();
    } catch (e) {
      _error = e.toString();
      _isLoading = false;
      notifyListeners();
    }
  }

  void setListening(bool listening) {
    _isListening = listening;
    notifyListeners();
  }

  Future<void> endConversation() async {
    if (_sessionId != null) {
      try {
        await _service.endSession(_sessionId!);
      } catch (_) {
        // ignore error on close
      }
    }
    await _webSocketService.disconnect();
    _sessionId = null;
    // Don't clear messages immediately if user wants to review?
    // Or clear them:
    // _messages = [];
    notifyListeners();
  }

  void clearError() {
    _error = null;
    notifyListeners();
  }
}

class ChatMessage {
  final String text;
  final bool isUser;
  final DateTime timestamp;

  ChatMessage({
    required this.text,
    required this.isUser,
    required this.timestamp,
  });
}
