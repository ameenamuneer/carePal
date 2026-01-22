import 'api_service.dart';

/// Alert Service - Complete implementation
/// Maps to backend/alerts/views.py endpoints
class AlertService {
  final ApiService _api = ApiService();

  // ==================== ALERT CRUD ====================

  /// Get list of alerts with optional filters
  /// GET /api/v1/alerts/alerts/
  Future<Map<String, dynamic>> getAlerts({
    int? patientId,
    String? severity,
    String? status,
    int? alertTypeId,
    bool? isEscalated,
    String? startDate,
    String? endDate,
    int page = 1,
    int pageSize = 20,
  }) async {
    try {
      final queryParams = <String, dynamic>{
        'page': page,
        'page_size': pageSize,
        if (patientId != null) 'patient': patientId,
        if (severity != null) 'severity': severity,
        if (status != null) 'status': status,
        if (alertTypeId != null) 'alert_type': alertTypeId,
        if (isEscalated != null) 'is_escalated': isEscalated,
        if (startDate != null) 'start_date': startDate,
        if (endDate != null) 'end_date': endDate,
      };

      final response = await _api.get(
        '/api/v1/alerts/alerts/',
        queryParameters: queryParams,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to load alerts: $e');
    }
  }

  /// Get a single alert by ID
  /// GET /api/v1/alerts/alerts/{id}/
  Future<Map<String, dynamic>> getAlert(int id) async {
    try {
      final response = await _api.get('/api/v1/alerts/alerts/$id/');
      return response.data;
    } catch (e) {
      throw Exception('Failed to load alert: $e');
    }
  }

  /// Create a new alert
  /// POST /api/v1/alerts/alerts/
  Future<Map<String, dynamic>> createAlert({
    required int patientId,
    required int alertTypeId,
    required String severity,
    required String title,
    required String message,
    String? source,
    Map<String, dynamic>? contextData,
    String? expiresAt,
  }) async {
    try {
      final data = {
        'patient': patientId,
        'alert_type': alertTypeId,
        'severity': severity,
        'title': title,
        'message': message,
        if (source != null) 'source': source,
        if (contextData != null) 'context_data': contextData,
        if (expiresAt != null) 'expires_at': expiresAt,
      };

      final response = await _api.post('/api/v1/alerts/alerts/', data: data);
      return response.data;
    } catch (e) {
      throw Exception('Failed to create alert: $e');
    }
  }

  /// Update an alert
  /// PUT /api/v1/alerts/alerts/{id}/
  Future<Map<String, dynamic>> updateAlert(
    int id,
    Map<String, dynamic> data,
  ) async {
    try {
      final response = await _api.put('/api/v1/alerts/alerts/$id/', data: data);
      return response.data;
    } catch (e) {
      throw Exception('Failed to update alert: $e');
    }
  }

  /// Delete an alert
  /// DELETE /api/v1/alerts/alerts/{id}/
  Future<void> deleteAlert(int id) async {
    try {
      await _api.delete('/api/v1/alerts/alerts/$id/');
    } catch (e) {
      throw Exception('Failed to delete alert: $e');
    }
  }

  // ==================== ALERT ACTIONS ====================

  /// Acknowledge an alert
  /// POST /api/v1/alerts/alerts/{id}/acknowledge/
  Future<Map<String, dynamic>> acknowledgeAlert(
    int id, {
    String? acknowledgmentNotes,
  }) async {
    try {
      final data = {
        if (acknowledgmentNotes != null)
          'acknowledgment_notes': acknowledgmentNotes,
      };

      final response = await _api.post(
        '/api/v1/alerts/alerts/$id/acknowledge/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to acknowledge alert: $e');
    }
  }

  /// Resolve an alert
  /// POST /api/v1/alerts/alerts/{id}/resolve/
  Future<Map<String, dynamic>> resolveAlert(
    int id, {
    required String resolutionNotes,
  }) async {
    try {
      final data = {'resolution_notes': resolutionNotes};

      final response = await _api.post(
        '/api/v1/alerts/alerts/$id/resolve/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to resolve alert: $e');
    }
  }

  /// Escalate an alert
  /// POST /api/v1/alerts/alerts/{id}/escalate/
  Future<Map<String, dynamic>> escalateAlert(
    int id, {
    String? reason,
    String? newSeverity,
  }) async {
    try {
      final data = {
        if (reason != null) 'reason': reason,
        if (newSeverity != null) 'severity': newSeverity,
      };

      final response = await _api.post(
        '/api/v1/alerts/alerts/$id/escalate/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to escalate alert: $e');
    }
  }

  // ==================== FILTERED ALERT LISTS ====================

  /// Get all active (unresolved) alerts
  /// GET /api/v1/alerts/alerts/active/
  Future<List<dynamic>> getActiveAlerts({int? patientId}) async {
    try {
      final queryParams = <String, dynamic>{
        if (patientId != null) 'patient_id': patientId,
      };

      final response = await _api.get(
        '/api/v1/alerts/alerts/active/',
        queryParameters: queryParams,
      );
      return response.data as List;
    } catch (e) {
      throw Exception('Failed to load active alerts: $e');
    }
  }

  /// Get critical and emergency alerts
  /// GET /api/v1/alerts/alerts/critical/
  Future<List<dynamic>> getCriticalAlerts({int? patientId}) async {
    try {
      final queryParams = <String, dynamic>{
        if (patientId != null) 'patient_id': patientId,
      };

      final response = await _api.get(
        '/api/v1/alerts/alerts/critical/',
        queryParameters: queryParams,
      );
      return response.data as List;
    } catch (e) {
      throw Exception('Failed to load critical alerts: $e');
    }
  }

  /// Get unacknowledged alerts
  /// GET /api/v1/alerts/alerts/unacknowledged/
  Future<List<dynamic>> getUnacknowledgedAlerts({int? patientId}) async {
    try {
      final queryParams = <String, dynamic>{
        if (patientId != null) 'patient_id': patientId,
      };

      final response = await _api.get(
        '/api/v1/alerts/alerts/unacknowledged/',
        queryParameters: queryParams,
      );
      return response.data as List;
    } catch (e) {
      throw Exception('Failed to load unacknowledged alerts: $e');
    }
  }

  // ==================== ALERT TYPES ====================

  /// Get all alert types
  /// GET /api/v1/alerts/types/
  Future<Map<String, dynamic>> getAlertTypes({
    String? category,
    String? severity,
    int page = 1,
    int pageSize = 50,
  }) async {
    try {
      final queryParams = <String, dynamic>{
        'page': page,
        'page_size': pageSize,
        if (category != null) 'category': category,
        if (severity != null) 'default_severity': severity,
      };

      final response = await _api.get(
        '/api/v1/alerts/types/',
        queryParameters: queryParams,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to load alert types: $e');
    }
  }

  /// Get a single alert type
  /// GET /api/v1/alerts/types/{id}/
  Future<Map<String, dynamic>> getAlertType(int id) async {
    try {
      final response = await _api.get('/api/v1/alerts/types/$id/');
      return response.data;
    } catch (e) {
      throw Exception('Failed to load alert type: $e');
    }
  }

  // ==================== ALERT RULES ====================

  /// Get alert rules
  /// GET /api/v1/alerts/rules/
  Future<Map<String, dynamic>> getAlertRules({
    int? patientId,
    int? alertTypeId,
    String? ruleType,
    bool? isActive,
    int page = 1,
    int pageSize = 20,
  }) async {
    try {
      final queryParams = <String, dynamic>{
        'page': page,
        'page_size': pageSize,
        if (patientId != null) 'patient': patientId,
        if (alertTypeId != null) 'alert_type': alertTypeId,
        if (ruleType != null) 'rule_type': ruleType,
        if (isActive != null) 'is_active': isActive,
      };

      final response = await _api.get(
        '/api/v1/alerts/rules/',
        queryParameters: queryParams,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to load alert rules: $e');
    }
  }

  /// Get a single alert rule
  /// GET /api/v1/alerts/rules/{id}/
  Future<Map<String, dynamic>> getAlertRule(int id) async {
    try {
      final response = await _api.get('/api/v1/alerts/rules/$id/');
      return response.data;
    } catch (e) {
      throw Exception('Failed to load alert rule: $e');
    }
  }

  /// Create an alert rule
  /// POST /api/v1/alerts/rules/
  Future<Map<String, dynamic>> createAlertRule(
    Map<String, dynamic> data,
  ) async {
    try {
      final response = await _api.post('/api/v1/alerts/rules/', data: data);
      return response.data;
    } catch (e) {
      throw Exception('Failed to create alert rule: $e');
    }
  }

  /// Update an alert rule
  /// PUT /api/v1/alerts/rules/{id}/
  Future<Map<String, dynamic>> updateAlertRule(
    int id,
    Map<String, dynamic> data,
  ) async {
    try {
      final response = await _api.put('/api/v1/alerts/rules/$id/', data: data);
      return response.data;
    } catch (e) {
      throw Exception('Failed to update alert rule: $e');
    }
  }

  /// Delete an alert rule
  /// DELETE /api/v1/alerts/rules/{id}/
  Future<void> deleteAlertRule(int id) async {
    try {
      await _api.delete('/api/v1/alerts/rules/$id/');
    } catch (e) {
      throw Exception('Failed to delete alert rule: $e');
    }
  }

  /// Test if a rule would trigger
  /// POST /api/v1/alerts/rules/{id}/test/
  Future<Map<String, dynamic>> testAlertRule(
    int id, {
    Map<String, dynamic>? testData,
  }) async {
    try {
      final data = {if (testData != null) 'test_data': testData};

      final response = await _api.post(
        '/api/v1/alerts/rules/$id/test/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to test alert rule: $e');
    }
  }

  // ==================== NOTIFICATION PREFERENCES ====================

  /// Get notification preferences
  /// GET /api/v1/alerts/preferences/
  Future<Map<String, dynamic>> getNotificationPreferences({
    int page = 1,
    int pageSize = 20,
  }) async {
    try {
      final queryParams = {'page': page, 'page_size': pageSize};

      final response = await _api.get(
        '/api/v1/alerts/preferences/',
        queryParameters: queryParams,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to load notification preferences: $e');
    }
  }

  /// Get current user's notification preferences
  /// GET /api/v1/alerts/preferences/my_preferences/
  Future<Map<String, dynamic>> getMyPreferences() async {
    try {
      final response = await _api.get(
        '/api/v1/alerts/preferences/my_preferences/',
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to load preferences: $e');
    }
  }

  /// Update current user's notification preferences
  /// PUT /api/v1/alerts/preferences/my_preferences/
  Future<Map<String, dynamic>> updateMyPreferences(
    Map<String, dynamic> data,
  ) async {
    try {
      final response = await _api.put(
        '/api/v1/alerts/preferences/my_preferences/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to update preferences: $e');
    }
  }

  /// Partially update current user's notification preferences
  /// PATCH /api/v1/alerts/preferences/my_preferences/
  Future<Map<String, dynamic>> patchMyPreferences(
    Map<String, dynamic> data,
  ) async {
    try {
      final response = await _api.patch(
        '/api/v1/alerts/preferences/my_preferences/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to patch preferences: $e');
    }
  }

  /// Get a specific notification preference
  /// GET /api/v1/alerts/preferences/{id}/
  Future<Map<String, dynamic>> getNotificationPreference(int id) async {
    try {
      final response = await _api.get('/api/v1/alerts/preferences/$id/');
      return response.data;
    } catch (e) {
      throw Exception('Failed to load notification preference: $e');
    }
  }

  /// Update a notification preference
  /// PUT /api/v1/alerts/preferences/{id}/
  Future<Map<String, dynamic>> updateNotificationPreference(
    int id,
    Map<String, dynamic> data,
  ) async {
    try {
      final response = await _api.put(
        '/api/v1/alerts/preferences/$id/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to update notification preference: $e');
    }
  }

  /// Partially update a notification preference
  /// PATCH /api/v1/alerts/preferences/{id}/
  Future<Map<String, dynamic>> patchNotificationPreference(
    int id,
    Map<String, dynamic> data,
  ) async {
    try {
      final response = await _api.patch(
        '/api/v1/alerts/preferences/$id/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to patch notification preference: $e');
    }
  }

  // ==================== ALERT DELIVERIES ====================

  /// Get alert deliveries
  /// GET /api/v1/alerts/deliveries/
  Future<Map<String, dynamic>> getAlertDeliveries({
    int? alertId,
    int? recipientId,
    String? channel,
    String? status,
    int page = 1,
    int pageSize = 20,
  }) async {
    try {
      final queryParams = <String, dynamic>{
        'page': page,
        'page_size': pageSize,
        if (alertId != null) 'alert': alertId,
        if (recipientId != null) 'recipient': recipientId,
        if (channel != null) 'channel': channel,
        if (status != null) 'status': status,
      };

      final response = await _api.get(
        '/api/v1/alerts/deliveries/',
        queryParameters: queryParams,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to load alert deliveries: $e');
    }
  }

  /// Get a single alert delivery
  /// GET /api/v1/alerts/deliveries/{id}/
  Future<Map<String, dynamic>> getAlertDelivery(int id) async {
    try {
      final response = await _api.get('/api/v1/alerts/deliveries/$id/');
      return response.data;
    } catch (e) {
      throw Exception('Failed to load alert delivery: $e');
    }
  }

  // ==================== ALERT STATISTICS ====================

  /// Get alert statistics
  /// GET /api/v1/alerts/statistics/
  Future<Map<String, dynamic>> getAlertStatistics({
    int? patientId,
    String? periodLabel,
    int page = 1,
    int pageSize = 20,
  }) async {
    try {
      final queryParams = <String, dynamic>{
        'page': page,
        'page_size': pageSize,
        if (patientId != null) 'patient': patientId,
        if (periodLabel != null) 'period_label': periodLabel,
      };

      final response = await _api.get(
        '/api/v1/alerts/statistics/',
        queryParameters: queryParams,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to load alert statistics: $e');
    }
  }

  /// Get a single alert statistics record
  /// GET /api/v1/alerts/statistics/{id}/
  Future<Map<String, dynamic>> getAlertStatistic(int id) async {
    try {
      final response = await _api.get('/api/v1/alerts/statistics/$id/');
      return response.data;
    } catch (e) {
      throw Exception('Failed to load alert statistic: $e');
    }
  }

  // ==================== ALERT DASHBOARD ====================

  /// Get alert dashboard data
  /// GET /api/v1/alerts/dashboard/
  Future<Map<String, dynamic>> getAlertDashboard({int? patientId}) async {
    try {
      final queryParams = <String, dynamic>{
        if (patientId != null) 'patient_id': patientId,
      };

      final response = await _api.get(
        '/api/v1/alerts/dashboard/',
        queryParameters: queryParams,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to load alert dashboard: $e');
    }
  }
}
