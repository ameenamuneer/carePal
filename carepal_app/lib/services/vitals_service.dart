import 'package:flutter/foundation.dart';
import 'api_service.dart';

/// EXPANDED Vitals Service - Complete Implementation
/// Maps to ALL endpoints in backend/vitals/views.py
///
/// ✅ Existing endpoints preserved (from original file)
/// ➕ NEW endpoints added based on backend code
class VitalsService {
  final ApiService _api = ApiService();

  // ==================== EXISTING ENDPOINTS (PRESERVED) ====================

  /// Get vitals readings with filters
  /// GET /api/v1/vitals/readings/
  Future<Map<String, dynamic>> getReadings({
    int? patientId,
    int? vitalTypeId,
    int? dataSourceId,
    bool? isAnomaly,
    String? anomalySeverity,
    String? sessionId,
    bool? isEdited,
    String? startDate,
    String? endDate,
    String? search,
    int page = 1,
    int pageSize = 20,
  }) async {
    try {
      final queryParams = <String, dynamic>{
        'page': page,
        'page_size': pageSize,
        if (patientId != null) 'patient': patientId,
        if (vitalTypeId != null) 'vital_type': vitalTypeId,
        if (dataSourceId != null) 'data_source': dataSourceId,
        if (isAnomaly != null) 'is_anomaly': isAnomaly,
        if (anomalySeverity != null) 'anomaly_severity': anomalySeverity,
        if (sessionId != null) 'session_id': sessionId,
        if (isEdited != null) 'is_edited': isEdited,
        if (startDate != null) 'start_date': startDate,
        if (endDate != null) 'end_date': endDate,
        if (search != null) 'search': search,
      };

      final response = await _api.get(
        '/api/v1/vitals/readings/',
        queryParameters: queryParams,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to load vitals: $e');
    }
  }

  /// Get latest reading for specific vital type
  /// Note: Uses custom action from backend
  /// GET /api/v1/vitals/readings/latest/
  Future<List<dynamic>> getLatestReadings({int? patientId}) async {
    try {
      final queryParams = <String, dynamic>{
        if (patientId != null) 'patient_id': patientId,
      };

      final response = await _api.get(
        '/api/v1/vitals/readings/latest/',
        queryParameters: queryParams,
      );
      return response.data as List;
    } catch (e) {
      throw Exception('Failed to load latest readings: $e');
    }
  }

  /// Create new vital reading (manual entry)
  /// POST /api/v1/vitals/readings/
  ///
  /// FIXED VERSION - Ensures correct ISO 8601 date format
  Future<Map<String, dynamic>> createReading({
    required int patientId,
    required int vitalTypeId,
    int? dataSourceId,
    double? value,
    Map<String, dynamic>? values,
    required String unit,
    DateTime? measuredAt,
    String? source,
    String? dataQuality,
    String? notes,
  }) async {
    try {
      // CRITICAL FIX: Format date as ISO 8601 with 'Z' timezone indicator
      final timestamp = measuredAt ?? DateTime.now();
      final isoTimestamp = timestamp.toUtc().toIso8601String();

      // CRITICAL FIX: Build data object with correct field types
      final data = <String, dynamic>{
        'patient': patientId,
        'vital_type': vitalTypeId,
        'unit': unit,
        'measured_at': isoTimestamp,
      };

      // Add optional data source
      if (dataSourceId != null) {
        data['data_source'] = dataSourceId;
      }

      // CRITICAL FIX: Only include value OR values, not both
      if (values != null && values.isNotEmpty) {
        data['values'] = values;
      } else if (value != null) {
        data['value'] = value;
      } else {
        throw Exception('Either value or values must be provided');
      }

      // Add optional fields
      if (source != null && source.isNotEmpty) {
        data['source'] = source;
      } else {
        data['source'] = 'MANUAL'; // Default to MANUAL for manual entries
      }

      if (dataQuality != null && dataQuality.isNotEmpty) {
        data['data_quality'] = dataQuality;
      }

      if (notes != null && notes.isNotEmpty) {
        data['notes'] = notes;
      }

      debugPrint('Creating vital reading with data: $data');

      final response = await _api.post('/api/v1/vitals/readings/', data: data);

      debugPrint('Vital reading created successfully: ${response.data}');
      return response.data;
    } catch (e) {
      debugPrint('Failed to create vital reading: $e');
      throw Exception('Failed to create vital reading: $e');
    }
  }

  /// Get vital types
  /// GET /api/v1/vitals/vital-types/
  Future<Map<String, dynamic>> getVitalTypes({
    String? category,
    bool? isContinuous,
    String? search,
    int page = 1,
    int pageSize = 50,
  }) async {
    try {
      final queryParams = <String, dynamic>{
        'page': page,
        'page_size': pageSize,
        if (category != null) 'category': category,
        if (isContinuous != null) 'is_continuous': isContinuous,
        if (search != null) 'search': search,
      };

      final response = await _api.get(
        '/api/v1/vitals/vital-types/',
        queryParameters: queryParams,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to load vital types: $e');
    }
  }

  /// Get statistics for a vital type
  /// Note: This might be computed in trends action instead
  Future<Map<String, dynamic>> getVitalStats({
    required int patientId,
    required int vitalTypeId,
    String period = '7days',
  }) async {
    try {
      final response = await _api.get(
        '/api/v1/vitals/readings/trends/',
        queryParameters: {
          'patient_id': patientId,
          'vital_type_id': vitalTypeId,
          'period': period,
        },
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to load vital stats: $e');
    }
  }

  // ==================== NEW VITAL READING ENDPOINTS ====================

  /// Get a single vital reading
  /// GET /api/v1/vitals/readings/{id}/
  Future<Map<String, dynamic>> getReading(int id) async {
    try {
      final response = await _api.get('/api/v1/vitals/readings/$id/');
      return response.data;
    } catch (e) {
      throw Exception('Failed to load reading: $e');
    }
  }

  /// Update a vital reading (admin only)
  /// PUT /api/v1/vitals/readings/{id}/
  Future<Map<String, dynamic>> updateReading(
    int id,
    Map<String, dynamic> data,
  ) async {
    try {
      final response = await _api.put(
        '/api/v1/vitals/readings/$id/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to update reading: $e');
    }
  }

  /// Partially update a vital reading (admin only)
  /// PATCH /api/v1/vitals/readings/{id}/
  Future<Map<String, dynamic>> patchReading(
    int id,
    Map<String, dynamic> data,
  ) async {
    try {
      final response = await _api.patch(
        '/api/v1/vitals/readings/$id/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to patch reading: $e');
    }
  }

  /// Soft delete a vital reading
  /// DELETE /api/v1/vitals/readings/{id}/
  Future<Map<String, dynamic>> deleteReading(int id) async {
    try {
      final response = await _api.delete('/api/v1/vitals/readings/$id/');
      return response.data;
    } catch (e) {
      throw Exception('Failed to delete reading: $e');
    }
  }

  /// Get edit history for a vital reading
  /// GET /api/v1/vitals/readings/{id}/edit_history/
  Future<List<dynamic>> getReadingEditHistory(int id) async {
    try {
      final response = await _api.get(
        '/api/v1/vitals/readings/$id/edit_history/',
      );
      return response.data as List;
    } catch (e) {
      throw Exception('Failed to load edit history: $e');
    }
  }

  /// Get trend data for a specific vital type
  /// GET /api/v1/vitals/readings/trends/
  Future<Map<String, dynamic>> getVitalTrends({
    required int patientId,
    required int vitalTypeId,
    String period = '7days', // 24h, 7days, 30days
  }) async {
    try {
      final response = await _api.get(
        '/api/v1/vitals/readings/trends/',
        queryParameters: {
          'patient_id': patientId,
          'vital_type_id': vitalTypeId,
          'period': period,
        },
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to load trends: $e');
    }
  }

  /// Get all anomalous readings
  /// GET /api/v1/vitals/readings/anomalies/
  Future<List<dynamic>> getAnomalousReadings({
    int? patientId,
    String? severity,
  }) async {
    try {
      final queryParams = <String, dynamic>{
        if (patientId != null) 'patient_id': patientId,
        if (severity != null) 'severity': severity,
      };

      final response = await _api.get(
        '/api/v1/vitals/readings/anomalies/',
        queryParameters: queryParams,
      );
      return response.data as List;
    } catch (e) {
      throw Exception('Failed to load anomalies: $e');
    }
  }

  /// Bulk create vital readings (for device sync)
  /// POST /api/v1/vitals/readings/bulk_create/
  Future<Map<String, dynamic>> bulkCreateReadings({
    required List<Map<String, dynamic>> readings,
  }) async {
    try {
      final data = {'readings': readings};

      final response = await _api.post(
        '/api/v1/vitals/readings/bulk_create/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to bulk create readings: $e');
    }
  }

  // ==================== NEW VITAL TYPE ENDPOINTS ====================

  /// Get a single vital type
  /// GET /api/v1/vitals/vital-types/{id}/
  Future<Map<String, dynamic>> getVitalType(int id) async {
    try {
      final response = await _api.get('/api/v1/vitals/vital-types/$id/');
      return response.data;
    } catch (e) {
      throw Exception('Failed to load vital type: $e');
    }
  }

  // ==================== NEW DATA SOURCE ENDPOINTS ====================

  /// Get data sources
  /// GET /api/v1/vitals/data-sources/
  Future<Map<String, dynamic>> getDataSources({
    int? patientId,
    String? sourceType,
    String? deviceType,
    bool? isActive,
    String? search,
    int page = 1,
    int pageSize = 20,
  }) async {
    try {
      final queryParams = <String, dynamic>{
        'page': page,
        'page_size': pageSize,
        if (patientId != null) 'patient': patientId,
        if (sourceType != null) 'source_type': sourceType,
        if (deviceType != null) 'device_type': deviceType,
        if (isActive != null) 'is_active': isActive,
        if (search != null) 'search': search,
      };

      final response = await _api.get(
        '/api/v1/vitals/data-sources/',
        queryParameters: queryParams,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to load data sources: $e');
    }
  }

  /// Get a single data source
  /// GET /api/v1/vitals/data-sources/{id}/
  Future<Map<String, dynamic>> getDataSource(int id) async {
    try {
      final response = await _api.get('/api/v1/vitals/data-sources/$id/');
      return response.data;
    } catch (e) {
      throw Exception('Failed to load data source: $e');
    }
  }

  /// Create a data source
  /// POST /api/v1/vitals/data-sources/
  Future<Map<String, dynamic>> createDataSource(
    Map<String, dynamic> data,
  ) async {
    try {
      final response = await _api.post(
        '/api/v1/vitals/data-sources/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to create data source: $e');
    }
  }

  /// Update a data source
  /// PUT /api/v1/vitals/data-sources/{id}/
  Future<Map<String, dynamic>> updateDataSource(
    int id,
    Map<String, dynamic> data,
  ) async {
    try {
      final response = await _api.put(
        '/api/v1/vitals/data-sources/$id/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to update data source: $e');
    }
  }

  /// Partially update a data source
  /// PATCH /api/v1/vitals/data-sources/{id}/
  Future<Map<String, dynamic>> patchDataSource(
    int id,
    Map<String, dynamic> data,
  ) async {
    try {
      final response = await _api.patch(
        '/api/v1/vitals/data-sources/$id/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to patch data source: $e');
    }
  }

  /// Delete a data source
  /// DELETE /api/v1/vitals/data-sources/{id}/
  Future<void> deleteDataSource(int id) async {
    try {
      await _api.delete('/api/v1/vitals/data-sources/$id/');
    } catch (e) {
      throw Exception('Failed to delete data source: $e');
    }
  }

  /// Trigger immediate sync for cloud-based data sources
  /// POST /api/v1/vitals/data-sources/{id}/sync_now/
  Future<Map<String, dynamic>> syncDataSource(int id) async {
    try {
      final response = await _api.post(
        '/api/v1/vitals/data-sources/$id/sync_now/',
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to sync data source: $e');
    }
  }

  // ==================== NEW CONTINUOUS SESSION ENDPOINTS ====================

  /// Get continuous vital sessions
  /// GET /api/v1/vitals/sessions/
  Future<Map<String, dynamic>> getContinuousSessions({
    int? patientId,
    int? vitalTypeId,
    String? status,
    int page = 1,
    int pageSize = 20,
  }) async {
    try {
      final queryParams = <String, dynamic>{
        'page': page,
        'page_size': pageSize,
        if (patientId != null) 'patient': patientId,
        if (vitalTypeId != null) 'vital_type': vitalTypeId,
        if (status != null) 'status': status,
      };

      final response = await _api.get(
        '/api/v1/vitals/sessions/',
        queryParameters: queryParams,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to load continuous sessions: $e');
    }
  }

  /// Get a single continuous session
  /// GET /api/v1/vitals/sessions/{id}/
  Future<Map<String, dynamic>> getContinuousSession(int id) async {
    try {
      final response = await _api.get('/api/v1/vitals/sessions/$id/');
      return response.data;
    } catch (e) {
      throw Exception('Failed to load continuous session: $e');
    }
  }

  /// Create a continuous vital session
  /// POST /api/v1/vitals/sessions/
  Future<Map<String, dynamic>> createContinuousSession(
    Map<String, dynamic> data,
  ) async {
    try {
      final response = await _api.post('/api/v1/vitals/sessions/', data: data);
      return response.data;
    } catch (e) {
      throw Exception('Failed to create continuous session: $e');
    }
  }

  /// Update a continuous session
  /// PUT /api/v1/vitals/sessions/{id}/
  Future<Map<String, dynamic>> updateContinuousSession(
    int id,
    Map<String, dynamic> data,
  ) async {
    try {
      final response = await _api.put(
        '/api/v1/vitals/sessions/$id/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to update continuous session: $e');
    }
  }

  /// Partially update a continuous session
  /// PATCH /api/v1/vitals/sessions/{id}/
  Future<Map<String, dynamic>> patchContinuousSession(
    int id,
    Map<String, dynamic> data,
  ) async {
    try {
      final response = await _api.patch(
        '/api/v1/vitals/sessions/$id/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to patch continuous session: $e');
    }
  }

  /// Delete a continuous session
  /// DELETE /api/v1/vitals/sessions/{id}/
  Future<void> deleteContinuousSession(int id) async {
    try {
      await _api.delete('/api/v1/vitals/sessions/$id/');
    } catch (e) {
      throw Exception('Failed to delete continuous session: $e');
    }
  }

  /// End a continuous monitoring session
  /// POST /api/v1/vitals/sessions/{id}/end_session/
  Future<Map<String, dynamic>> endContinuousSession(int id) async {
    try {
      final response = await _api.post(
        '/api/v1/vitals/sessions/$id/end_session/',
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to end continuous session: $e');
    }
  }

  // ==================== NEW TREND ANALYSIS ENDPOINTS ====================

  /// Get vital trend analyses
  /// GET /api/v1/vitals/trends/
  Future<Map<String, dynamic>> getTrendAnalyses({
    int? patientId,
    int? vitalTypeId,
    String? periodLabel,
    String? trendDirection,
    int page = 1,
    int pageSize = 20,
  }) async {
    try {
      final queryParams = <String, dynamic>{
        'page': page,
        'page_size': pageSize,
        if (patientId != null) 'patient': patientId,
        if (vitalTypeId != null) 'vital_type': vitalTypeId,
        if (periodLabel != null) 'period_label': periodLabel,
        if (trendDirection != null) 'trend_direction': trendDirection,
      };

      final response = await _api.get(
        '/api/v1/vitals/trends/',
        queryParameters: queryParams,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to load trend analyses: $e');
    }
  }

  /// Get a single trend analysis
  /// GET /api/v1/vitals/trends/{id}/
  Future<Map<String, dynamic>> getTrendAnalysis(int id) async {
    try {
      final response = await _api.get('/api/v1/vitals/trends/$id/');
      return response.data;
    } catch (e) {
      throw Exception('Failed to load trend analysis: $e');
    }
  }

  // ==================== NEW DASHBOARD ENDPOINTS ====================

  /// Get complete vitals summary for dashboard
  /// GET /api/v1/vitals/dashboard/vitals_summary/
  Future<List<dynamic>> getVitalsSummary({int? patientId}) async {
    try {
      final queryParams = <String, dynamic>{
        if (patientId != null) 'patient_id': patientId,
      };

      final response = await _api.get(
        '/api/v1/vitals/dashboard/vitals_summary/',
        queryParameters: queryParams,
      );
      return response.data as List;
    } catch (e) {
      throw Exception('Failed to load vitals summary: $e');
    }
  }
}
