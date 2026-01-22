import 'api_service.dart';

/// CORRECTED AI Agent Service
/// Maps to backend/agent/views.py AgentSessionViewSet
/// Routes: /api/v1/agent/sessions/
class AIAgentService {
  final ApiService _api = ApiService();

  // ==================== AGENT SESSIONS (ModelViewSet) ====================

  /// Get list of agent sessions
  /// GET /api/v1/agent/sessions/
  Future<Map<String, dynamic>> getSessions({
    int? patientId,
    String? sessionType,
    String? status,
    String? language,
    int page = 1,
    int pageSize = 20,
  }) async {
    try {
      final queryParams = <String, dynamic>{
        'page': page,
        'page_size': pageSize,
        if (patientId != null) 'patient': patientId,
        if (sessionType != null) 'session_type': sessionType,
        if (status != null) 'status': status,
        if (language != null) 'language': language,
      };

      final response = await _api.get(
        '/api/v1/agent/sessions/',
        queryParameters: queryParams,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to load sessions: $e');
    }
  }

  /// Get a single agent session (includes messages and actions)
  /// GET /api/v1/agent/sessions/{id}/
  Future<Map<String, dynamic>> getSession(int id) async {
    try {
      final response = await _api.get('/api/v1/agent/sessions/$id/');
      return response.data;
    } catch (e) {
      throw Exception('Failed to load session: $e');
    }
  }

  /// Create a new agent session (manual start)
  /// POST /api/v1/agent/sessions/
  Future<Map<String, dynamic>> createSession({
    required int patientId,
    String sessionType = 'WEBSOCKET',
    String language = 'en',
    Map<String, dynamic>? metadata,
  }) async {
    try {
      final data = {
        'patient': patientId,
        'session_type': sessionType,
        'language': language,
        if (metadata != null) 'metadata': metadata,
      };

      final response = await _api.post('/api/v1/agent/sessions/', data: data);
      return response.data;
    } catch (e) {
      throw Exception('Failed to create session: $e');
    }
  }

  /// Update an agent session
  /// PUT /api/v1/agent/sessions/{id}/
  Future<Map<String, dynamic>> updateSession(
    int id,
    Map<String, dynamic> data,
  ) async {
    try {
      final response = await _api.put(
        '/api/v1/agent/sessions/$id/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to update session: $e');
    }
  }

  /// Partially update an agent session
  /// PATCH /api/v1/agent/sessions/{id}/
  Future<Map<String, dynamic>> patchSession(
    int id,
    Map<String, dynamic> data,
  ) async {
    try {
      final response = await _api.patch(
        '/api/v1/agent/sessions/$id/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to patch session: $e');
    }
  }

  /// Delete an agent session
  /// DELETE /api/v1/agent/sessions/{id}/
  Future<void> deleteSession(int id) async {
    try {
      await _api.delete('/api/v1/agent/sessions/$id/');
    } catch (e) {
      throw Exception('Failed to delete session: $e');
    }
  }

  /// End an active session
  /// POST /api/v1/agent/sessions/{id}/end_session/
  Future<Map<String, dynamic>> endSession(int id) async {
    try {
      final response = await _api.post(
        '/api/v1/agent/sessions/$id/end_session/',
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to end session: $e');
    }
  }

  // ==================== HELPER METHODS ====================

  /// Get session messages (from session detail)
  Future<List<dynamic>> getSessionMessages(int sessionId) async {
    try {
      final session = await getSession(sessionId);
      return session['messages'] as List? ?? [];
    } catch (e) {
      throw Exception('Failed to load session messages: $e');
    }
  }

  /// Get session actions (from session detail)
  Future<List<dynamic>> getSessionActions(int sessionId) async {
    try {
      final session = await getSession(sessionId);
      return session['actions'] as List? ?? [];
    } catch (e) {
      throw Exception('Failed to load session actions: $e');
    }
  }
}
