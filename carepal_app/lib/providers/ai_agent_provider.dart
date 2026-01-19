import 'package:flutter/foundation.dart';
import '../services/ai_agent_service.dart';

class AIAgentProvider with ChangeNotifier {
  final AIAgentService _service = AIAgentService();

  String? _sessionId;
  List<ChatMessage> _messages = [];
  bool _isLoading = false;
  bool _isListening = false;
  String? _error;

  String? get sessionId => _sessionId;
  List<ChatMessage> get messages => _messages;
  bool get isLoading => _isLoading;
  bool get isListening => _isListening;
  String? get error => _error;

  Future<void> startConversation(int patientId) async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final response = await _service.startConversation(patientId);
      _sessionId = response['session_id'];
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
    if (_sessionId == null) return;

    // Add user message
    _messages.add(
      ChatMessage(text: message, isUser: true, timestamp: DateTime.now()),
    );
    notifyListeners();

    _isLoading = true;

    try {
      final response = await _service.sendMessage(
        sessionId: _sessionId!,
        message: message,
      );

      // Add AI response
      _messages.add(
        ChatMessage(
          text: response['ai_response'] ?? 'Sorry, I did not understand.',
          isUser: false,
          timestamp: DateTime.now(),
        ),
      );

      _isLoading = false;
      _error = null;
      notifyListeners();
    } catch (e) {
      _error = e.toString();
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<void> loadHistory() async {
    if (_sessionId == null) return;

    _isLoading = true;
    notifyListeners();

    try {
      final history = await _service.getConversationHistory(_sessionId!);
      _messages = history.map((msg) {
        return ChatMessage(
          text: msg['content'],
          isUser: msg['role'] == 'user',
          timestamp: DateTime.parse(msg['timestamp']),
        );
      }).toList();

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
      await _service.endConversation(_sessionId!);
    }
    _sessionId = null;
    _messages = [];
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
