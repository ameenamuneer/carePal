import 'api_service.dart';

/// EXPANDED Medication Service - Complete Implementation
/// Maps to ALL endpoints in backend/medications/views.py
///
/// ✅ Existing endpoints preserved (from original file)
/// ➕ NEW endpoints added based on backend code
class MedicationService {
  final ApiService _api = ApiService();

  // ==================== EXISTING ENDPOINTS (PRESERVED) ====================

  /// Get today's medication schedule
  /// GET /api/v1/medications/adherence/today/
  Future<List<dynamic>> getTodaysSchedule({int? patientId}) async {
    try {
      final queryParams = <String, dynamic>{
        if (patientId != null) 'patient_id': patientId,
      };

      final response = await _api.get(
        '/api/v1/medications/adherence/today/',
        queryParameters: queryParams,
      );
      return response.data as List;
    } catch (e) {
      throw Exception('Failed to load today\'s schedule: $e');
    }
  }

  /// Get all medications with optional status filter
  /// GET /api/v1/medications/medications/
  Future<Map<String, dynamic>> getMedications({
    String? status,
    String? form,
    String? route,
    bool? isCritical,
    String? search,
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

  /// Mark medication adherence as taken
  /// POST /api/v1/medications/adherence/{id}/mark_taken/
  Future<Map<String, dynamic>> markAdherenceTaken({
    required int adherenceId,
    String? confirmationMethod,
    String? notes,
  }) async {
    try {
      final data = {
        'confirmation_method': confirmationMethod ?? 'app',
        if (notes != null) 'notes': notes,
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

  /// Mark medication adherence as skipped
  /// POST /api/v1/medications/adherence/{id}/mark_skipped/
  Future<Map<String, dynamic>> markAdherenceSkipped({
    required int adherenceId,
    required String reason,
  }) async {
    try {
      final data = {'skip_reason': reason};

      final response = await _api.post(
        '/api/v1/medications/adherence/$adherenceId/mark_skipped/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to mark as skipped: $e');
    }
  }

  /// Get adherence history
  /// GET /api/v1/medications/adherence/
  Future<Map<String, dynamic>> getAdherenceHistory({
    int? medicationId,
    String? status,
    String? scheduledDate,
    int page = 1,
    int pageSize = 20,
  }) async {
    try {
      final queryParams = <String, dynamic>{
        'page': page,
        'page_size': pageSize,
        if (medicationId != null) 'medication': medicationId,
        if (status != null) 'status': status,
        if (scheduledDate != null) 'scheduled_date': scheduledDate,
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

  /// Get adherence rate
  /// Note: This endpoint path doesn't exist in backend - using patterns instead
  /// GET /api/v1/medications/patterns/ with calculation
  Future<double> getAdherenceRate({int? patientId, int days = 7}) async {
    try {
      // Using adherence patterns to calculate rate
      final patterns = await getAdherencePatterns(
        patientId: patientId,
        periodLabel: 'last_${days}days',
      );

      if (patterns['results'] != null &&
          (patterns['results'] as List).isNotEmpty) {
        final latest = patterns['results'][0];
        return (latest['adherence_rate'] as num).toDouble();
      }

      return 0.0;
    } catch (e) {
      throw Exception('Failed to get adherence rate: $e');
    }
  }

  // ==================== NEW MEDICATION CRUD ENDPOINTS ====================

  /// Get a single medication
  /// GET /api/v1/medications/medications/{id}/
  Future<Map<String, dynamic>> getMedication(int id) async {
    try {
      final response = await _api.get('/api/v1/medications/medications/$id/');
      return response.data;
    } catch (e) {
      throw Exception('Failed to load medication: $e');
    }
  }

  /// Create a new medication
  /// POST /api/v1/medications/medications/
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

  /// Update a medication
  /// PUT /api/v1/medications/medications/{id}/
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

  /// Partially update a medication
  /// PATCH /api/v1/medications/medications/{id}/
  Future<Map<String, dynamic>> patchMedication(
    int id,
    Map<String, dynamic> data,
  ) async {
    try {
      final response = await _api.patch(
        '/api/v1/medications/medications/$id/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to patch medication: $e');
    }
  }

  /// Delete a medication
  /// DELETE /api/v1/medications/medications/{id}/
  Future<void> deleteMedication(int id) async {
    try {
      await _api.delete('/api/v1/medications/medications/$id/');
    } catch (e) {
      throw Exception('Failed to delete medication: $e');
    }
  }

  // ==================== NEW MEDICATION ACTIONS ====================

  /// Discontinue a medication
  /// POST /api/v1/medications/medications/{id}/discontinue/
  Future<Map<String, dynamic>> discontinueMedication(
    int id, {
    required String reason,
  }) async {
    try {
      final data = {'reason': reason};

      final response = await _api.post(
        '/api/v1/medications/medications/$id/discontinue/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to discontinue medication: $e');
    }
  }

  /// Resume a discontinued medication
  /// POST /api/v1/medications/medications/{id}/resume/
  Future<Map<String, dynamic>> resumeMedication(int id) async {
    try {
      final response = await _api.post(
        '/api/v1/medications/medications/$id/resume/',
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to resume medication: $e');
    }
  }

  /// Get adherence summary for a medication
  /// GET /api/v1/medications/medications/{id}/adherence_summary/
  Future<Map<String, dynamic>> getMedicationAdherenceSummary(
    int id, {
    String period = '7days',
  }) async {
    try {
      final response = await _api.get(
        '/api/v1/medications/medications/$id/adherence_summary/',
        queryParameters: {'period': period},
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to load adherence summary: $e');
    }
  }

  /// Get all active medications
  /// GET /api/v1/medications/medications/active/
  Future<List<dynamic>> getActiveMedications({int? patientId}) async {
    try {
      final queryParams = <String, dynamic>{
        if (patientId != null) 'patient_id': patientId,
      };

      final response = await _api.get(
        '/api/v1/medications/medications/active/',
        queryParameters: queryParams,
      );
      return response.data as List;
    } catch (e) {
      throw Exception('Failed to load active medications: $e');
    }
  }

  /// Get medications that need refill
  /// GET /api/v1/medications/medications/needs_refill/
  Future<List<dynamic>> getMedicationsNeedingRefill({int? patientId}) async {
    try {
      final queryParams = <String, dynamic>{
        if (patientId != null) 'patient_id': patientId,
      };

      final response = await _api.get(
        '/api/v1/medications/medications/needs_refill/',
        queryParameters: queryParams,
      );
      return response.data as List;
    } catch (e) {
      throw Exception('Failed to load medications needing refill: $e');
    }
  }

  // ==================== NEW ADHERENCE ACTIONS ====================

  /// Get upcoming medication doses
  /// GET /api/v1/medications/adherence/upcoming/
  Future<List<dynamic>> getUpcomingDoses({int? patientId}) async {
    try {
      final queryParams = <String, dynamic>{
        if (patientId != null) 'patient_id': patientId,
      };

      final response = await _api.get(
        '/api/v1/medications/adherence/upcoming/',
        queryParameters: queryParams,
      );
      return response.data as List;
    } catch (e) {
      throw Exception('Failed to load upcoming doses: $e');
    }
  }

  /// Get overdue medication doses
  /// GET /api/v1/medications/adherence/overdue/
  Future<List<dynamic>> getOverdueDoses({int? patientId}) async {
    try {
      final queryParams = <String, dynamic>{
        if (patientId != null) 'patient_id': patientId,
      };

      final response = await _api.get(
        '/api/v1/medications/adherence/overdue/',
        queryParameters: queryParams,
      );
      return response.data as List;
    } catch (e) {
      throw Exception('Failed to load overdue doses: $e');
    }
  }

  /// Get a single adherence record
  /// GET /api/v1/medications/adherence/{id}/
  Future<Map<String, dynamic>> getAdherenceRecord(int id) async {
    try {
      final response = await _api.get('/api/v1/medications/adherence/$id/');
      return response.data;
    } catch (e) {
      throw Exception('Failed to load adherence record: $e');
    }
  }

  /// Update an adherence record
  /// PUT /api/v1/medications/adherence/{id}/
  Future<Map<String, dynamic>> updateAdherenceRecord(
    int id,
    Map<String, dynamic> data,
  ) async {
    try {
      final response = await _api.put(
        '/api/v1/medications/adherence/$id/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to update adherence record: $e');
    }
  }

  /// Partially update an adherence record
  /// PATCH /api/v1/medications/adherence/{id}/
  Future<Map<String, dynamic>> patchAdherenceRecord(
    int id,
    Map<String, dynamic> data,
  ) async {
    try {
      final response = await _api.patch(
        '/api/v1/medications/adherence/$id/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to patch adherence record: $e');
    }
  }

  // ==================== NEW SCHEDULES ENDPOINTS ====================

  /// Get medication schedules
  /// GET /api/v1/medications/schedules/
  Future<Map<String, dynamic>> getMedicationSchedules({
    int? medicationId,
    int page = 1,
    int pageSize = 20,
  }) async {
    try {
      final queryParams = <String, dynamic>{
        'page': page,
        'page_size': pageSize,
        if (medicationId != null) 'medication': medicationId,
      };

      final response = await _api.get(
        '/api/v1/medications/schedules/',
        queryParameters: queryParams,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to load medication schedules: $e');
    }
  }

  /// Get a single medication schedule
  /// GET /api/v1/medications/schedules/{id}/
  Future<Map<String, dynamic>> getMedicationSchedule(int id) async {
    try {
      final response = await _api.get('/api/v1/medications/schedules/$id/');
      return response.data;
    } catch (e) {
      throw Exception('Failed to load medication schedule: $e');
    }
  }

  /// Create a medication schedule
  /// POST /api/v1/medications/schedules/
  Future<Map<String, dynamic>> createMedicationSchedule(
    Map<String, dynamic> data,
  ) async {
    try {
      final response = await _api.post(
        '/api/v1/medications/schedules/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to create medication schedule: $e');
    }
  }

  /// Update a medication schedule
  /// PUT /api/v1/medications/schedules/{id}/
  Future<Map<String, dynamic>> updateMedicationSchedule(
    int id,
    Map<String, dynamic> data,
  ) async {
    try {
      final response = await _api.put(
        '/api/v1/medications/schedules/$id/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to update medication schedule: $e');
    }
  }

  /// Partially update a medication schedule
  /// PATCH /api/v1/medications/schedules/{id}/
  Future<Map<String, dynamic>> patchMedicationSchedule(
    int id,
    Map<String, dynamic> data,
  ) async {
    try {
      final response = await _api.patch(
        '/api/v1/medications/schedules/$id/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to patch medication schedule: $e');
    }
  }

  /// Delete a medication schedule
  /// DELETE /api/v1/medications/schedules/{id}/
  Future<void> deleteMedicationSchedule(int id) async {
    try {
      await _api.delete('/api/v1/medications/schedules/$id/');
    } catch (e) {
      throw Exception('Failed to delete medication schedule: $e');
    }
  }

  // ==================== NEW REFILLS ENDPOINTS ====================

  /// Get medication refills
  /// GET /api/v1/medications/refills/
  Future<Map<String, dynamic>> getMedicationRefills({
    int? medicationId,
    String? status,
    int page = 1,
    int pageSize = 20,
  }) async {
    try {
      final queryParams = <String, dynamic>{
        'page': page,
        'page_size': pageSize,
        if (medicationId != null) 'medication': medicationId,
        if (status != null) 'status': status,
      };

      final response = await _api.get(
        '/api/v1/medications/refills/',
        queryParameters: queryParams,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to load medication refills: $e');
    }
  }

  /// Get a single medication refill
  /// GET /api/v1/medications/refills/{id}/
  Future<Map<String, dynamic>> getMedicationRefill(int id) async {
    try {
      final response = await _api.get('/api/v1/medications/refills/$id/');
      return response.data;
    } catch (e) {
      throw Exception('Failed to load medication refill: $e');
    }
  }

  /// Create a medication refill request
  /// POST /api/v1/medications/refills/
  Future<Map<String, dynamic>> createMedicationRefill(
    Map<String, dynamic> data,
  ) async {
    try {
      final response = await _api.post(
        '/api/v1/medications/refills/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to create medication refill: $e');
    }
  }

  /// Update a medication refill
  /// PUT /api/v1/medications/refills/{id}/
  Future<Map<String, dynamic>> updateMedicationRefill(
    int id,
    Map<String, dynamic> data,
  ) async {
    try {
      final response = await _api.put(
        '/api/v1/medications/refills/$id/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to update medication refill: $e');
    }
  }

  /// Partially update a medication refill
  /// PATCH /api/v1/medications/refills/{id}/
  Future<Map<String, dynamic>> patchMedicationRefill(
    int id,
    Map<String, dynamic> data,
  ) async {
    try {
      final response = await _api.patch(
        '/api/v1/medications/refills/$id/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to patch medication refill: $e');
    }
  }

  /// Delete a medication refill
  /// DELETE /api/v1/medications/refills/{id}/
  Future<void> deleteMedicationRefill(int id) async {
    try {
      await _api.delete('/api/v1/medications/refills/$id/');
    } catch (e) {
      throw Exception('Failed to delete medication refill: $e');
    }
  }

  /// Approve a refill request (doctor/admin only)
  /// POST /api/v1/medications/refills/{id}/approve/
  Future<Map<String, dynamic>> approveRefill(int id) async {
    try {
      final response = await _api.post(
        '/api/v1/medications/refills/$id/approve/',
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to approve refill: $e');
    }
  }

  /// Mark refill as filled
  /// POST /api/v1/medications/refills/{id}/mark_filled/
  Future<Map<String, dynamic>> markRefillFilled(
    int id, {
    String? filledDate,
  }) async {
    try {
      final data = {if (filledDate != null) 'filled_date': filledDate};

      final response = await _api.post(
        '/api/v1/medications/refills/$id/mark_filled/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to mark refill as filled: $e');
    }
  }

  // ==================== NEW INTERACTIONS ENDPOINTS ====================

  /// Get medication interactions
  /// GET /api/v1/medications/interactions/
  Future<Map<String, dynamic>> getMedicationInteractions({
    String? severity,
    bool? isActive,
    int page = 1,
    int pageSize = 20,
  }) async {
    try {
      final queryParams = <String, dynamic>{
        'page': page,
        'page_size': pageSize,
        if (severity != null) 'severity': severity,
        if (isActive != null) 'is_active': isActive,
      };

      final response = await _api.get(
        '/api/v1/medications/interactions/',
        queryParameters: queryParams,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to load medication interactions: $e');
    }
  }

  /// Get a single medication interaction
  /// GET /api/v1/medications/interactions/{id}/
  Future<Map<String, dynamic>> getMedicationInteraction(int id) async {
    try {
      final response = await _api.get('/api/v1/medications/interactions/$id/');
      return response.data;
    } catch (e) {
      throw Exception('Failed to load medication interaction: $e');
    }
  }

  /// Acknowledge a medication interaction (doctor/admin only)
  /// POST /api/v1/medications/interactions/{id}/acknowledge/
  Future<Map<String, dynamic>> acknowledgeMedicationInteraction(
    int id, {
    String? overrideReason,
  }) async {
    try {
      final data = {
        if (overrideReason != null) 'override_reason': overrideReason,
      };

      final response = await _api.post(
        '/api/v1/medications/interactions/$id/acknowledge/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to acknowledge interaction: $e');
    }
  }

  // ==================== NEW ADHERENCE PATTERNS ENDPOINTS ====================

  /// Get medication adherence patterns (read-only)
  /// GET /api/v1/medications/patterns/
  Future<Map<String, dynamic>> getAdherencePatterns({
    int? patientId,
    int? medicationId,
    String? periodLabel,
    int page = 1,
    int pageSize = 20,
  }) async {
    try {
      final queryParams = <String, dynamic>{
        'page': page,
        'page_size': pageSize,
        if (patientId != null) 'patient': patientId,
        if (medicationId != null) 'medication': medicationId,
        if (periodLabel != null) 'period_label': periodLabel,
      };

      final response = await _api.get(
        '/api/v1/medications/patterns/',
        queryParameters: queryParams,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to load adherence patterns: $e');
    }
  }

  /// Get a single adherence pattern
  /// GET /api/v1/medications/patterns/{id}/
  Future<Map<String, dynamic>> getAdherencePattern(int id) async {
    try {
      final response = await _api.get('/api/v1/medications/patterns/$id/');
      return response.data;
    } catch (e) {
      throw Exception('Failed to load adherence pattern: $e');
    }
  }
}
