import 'api_service.dart';

class AIAgentService {
  final ApiService _apiService = ApiService();

  Future<Map<String, dynamic>> startConversation(int patientId) async {
    try {
      final response = await _apiService.post(
        '/api/v1/ai-agent/conversations/start/',
        data: {'patient_id': patientId},
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to start conversation: $e');
    }
  }

  Future<Map<String, dynamic>> sendMessage({
    required String sessionId,
    required String message,
    String mode = 'text',
  }) async {
    try {
      final response = await _apiService.post(
        '/api/v1/ai-agent/conversations/$sessionId/message/',
        data: {'user_message': message, 'mode': mode},
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to send message: $e');
    }
  }

  Future<List<dynamic>> getConversationHistory(String sessionId) async {
    try {
      final response = await _apiService.get(
        '/api/v1/ai-agent/conversations/$sessionId/history/',
      );
      return response.data['messages'] ?? [];
    } catch (e) {
      throw Exception('Failed to get conversation history: $e');
    }
  }

  Future<void> endConversation(String sessionId) async {
    try {
      await _apiService.post('/api/v1/ai-agent/conversations/$sessionId/end/');
    } catch (e) {
      throw Exception('Failed to end conversation: $e');
    }
  }
}
