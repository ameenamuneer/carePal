import 'api_service.dart';

class MedicationService {
  final ApiService _api = ApiService();

  /// Get all medications with filters
  Future<Map<String, dynamic>> getMedications({
    String? status,
    String? form,
    String? route,
    bool? isCritical,
    String? search,
    int? patientId,
    int page = 1,
    int pageSize = 20,
  }) async {
    try {
      final queryParams = <String, dynamic>{
        'page': page,
        'page_size': pageSize,
        if (status != null) 'status': status,
        if (form != null) 'form': form,
        if (route != null) 'route': route,
        if (isCritical != null) 'is_critical': isCritical,
        if (search != null) 'search': search,
        if (patientId != null) 'patient_id': patientId,
      };

      final response = await _api.get(
        '/api/v1/medications/medications/',
        queryParameters: queryParams,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to load medications: $e');
    }
  }

  /// Create new medication
  Future<Map<String, dynamic>> createMedication(
    Map<String, dynamic> data,
  ) async {
    try {
      final response = await _api.post(
        '/api/v1/medications/medications/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to create medication: $e');
    }
  }

  /// Update medication
  Future<Map<String, dynamic>> updateMedication(
    int id,
    Map<String, dynamic> data,
  ) async {
    try {
      final response = await _api.put(
        '/api/v1/medications/medications/$id/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to update medication: $e');
    }
  }

  /// Delete medication
  Future<void> deleteMedication(int id) async {
    try {
      await _api.delete('/api/v1/medications/medications/$id/');
    } catch (e) {
      throw Exception('Failed to delete medication: $e');
    }
  }

  /// Check for duplicate medication before creating
  /// Returns list of similar existing medications
  Future<List<Map<String, dynamic>>> checkDuplicate({
    required String name,
    required String dosage,
    required String frequency,
    required int patientId,
  }) async {
    try {
      final response = await _api.post(
        '/api/v1/medications/medications/check_duplicate/',
        data: {
          'medication_name': name,
          'dosage': dosage,
          'frequency': frequency,
          'patient': patientId,
        },
      );
      final matches = response.data['matches'] as List? ?? [];
      return matches.cast<Map<String, dynamic>>();
    } catch (e) {
      // Don't block adding if check fails
      return [];
    }
  }

  /// Get medication schedule for a given date (defaults to today).
  /// Pass [date] as 'YYYY-MM-DD' to fetch any day's schedule (past or future).
  Future<List<dynamic>> getTodaysSchedule({int? patientId, String? date}) async {
    try {
      final queryParams = <String, dynamic>{
        if (patientId != null) 'patient_id': patientId,
        if (date != null) 'date': date,
      };

      final response = await _api.get(
        '/api/v1/medications/adherence/schedule/',
        queryParameters: queryParams,
      );
      return response.data as List;
    } catch (e) {
      throw Exception('Failed to load schedule: $e');
    }
  }

  /// Get adherence rate
  Future<Map<String, dynamic>> getAdherenceRate({
    int days = 7,
    int? patientId,
  }) async {
    try {
      final queryParams = <String, dynamic>{
        'days': days,
        if (patientId != null) 'patient_id': patientId,
      };

      final response = await _api.get(
        '/api/v1/medications/adherence/rate/',
        queryParameters: queryParams,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to load adherence rate: $e');
    }
  }

  /// Mark medication as taken
  Future<Map<String, dynamic>> markAdherenceTaken({
    required int adherenceId,
    String? confirmationMethod,
    String? notes,
  }) async {
    try {
      final data = {
        'confirmation_method': confirmationMethod ?? 'MANUAL',
        if (notes != null && notes.isNotEmpty) 'notes': notes,
      };

      final response = await _api.post(
        '/api/v1/medications/adherence/$adherenceId/mark_taken/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to mark as taken: $e');
    }
  }

  /// Mark medication as skipped
  Future<Map<String, dynamic>> markAdherenceSkipped({
    required int adherenceId,
    required String reason,
    String? notes,
  }) async {
    try {
      final data = {
        'skip_reason': reason,
        if (notes != null && notes.isNotEmpty) 'notes': notes,
      };

      final response = await _api.post(
        '/api/v1/medications/adherence/$adherenceId/mark_skipped/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to mark as skipped: $e');
    }
  }

  /// Get per-day adherence summary for calendar colouring.
  /// Returns map of { "YYYY-MM-DD": { total, taken, missed, skipped, scheduled } }
  Future<Map<String, dynamic>> getCalendarSummary({
    required int patientId,
    int monthsBack = 2,
  }) async {
    try {
      final response = await _api.get(
        '/api/v1/medications/adherence/calendar_summary/',
        queryParameters: {'patient_id': patientId, 'months_back': monthsBack},
      );
      return Map<String, dynamic>.from(response.data as Map);
    } catch (e) {
      throw Exception('Failed to load calendar summary: $e');
    }
  }

  /// Get adherence history with patient filter
  Future<Map<String, dynamic>> getAdherenceHistory({
    int? medicationId,
    int? patientId,
    String? status,
    String? dateFrom,
    String? dateTo,
    int page = 1,
    int pageSize = 20,
  }) async {
    try {
      final queryParams = <String, dynamic>{
        'page': page,
        'page_size': pageSize,
        if (medicationId != null) 'medication': medicationId,
        if (patientId != null) 'patient': patientId,
        if (status != null) 'status': status,
        if (dateFrom != null) 'date_from': dateFrom,
        if (dateTo != null) 'date_to': dateTo,
      };

      final response = await _api.get(
        '/api/v1/medications/adherence/',
        queryParameters: queryParams,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to load adherence history: $e');
    }
  }
}
