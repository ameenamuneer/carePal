import 'api_service.dart';

class MedicationService {
  final ApiService _api = ApiService();

  // ==================== MEDICATIONS ====================

  /// Get all medications with filters
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

  /// Get single medication with full details
  /// GET /api/v1/medications/medications/{id}/
  Future<Map<String, dynamic>> getMedication(int id) async {
    try {
      final response = await _api.get('/api/v1/medications/medications/$id/');
      return response.data;
    } catch (e) {
      throw Exception('Failed to load medication: $e');
    }
  }

  /// Get active medications
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
  Future<List<dynamic>> getMedicationsNeedingRefill() async {
    try {
      final response = await _api.get(
        '/api/v1/medications/medications/needs_refill/',
      );
      return response.data as List;
    } catch (e) {
      throw Exception('Failed to load medications needing refill: $e');
    }
  }

  /// Create new medication
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

  /// Update medication
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

  /// Discontinue medication
  /// POST /api/v1/medications/medications/{id}/discontinue/
  Future<Map<String, dynamic>> discontinueMedication(
    int id,
    String reason,
  ) async {
    try {
      final response = await _api.post(
        '/api/v1/medications/medications/$id/discontinue/',
        data: {'reason': reason},
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to discontinue medication: $e');
    }
  }

  /// Resume medication
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

  /// Get adherence summary for medication
  /// GET /api/v1/medications/medications/{id}/adherence_summary/
  Future<Map<String, dynamic>> getMedicationAdherenceSummary(
    int id, {
    int days = 7,
  }) async {
    try {
      final response = await _api.get(
        '/api/v1/medications/medications/$id/adherence_summary/',
        queryParameters: {'days': days},
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to load adherence summary: $e');
    }
  }

  /// Import prescription from Eka.Care
  /// POST /api/v1/medications/medications/import_prescription/
  Future<List<dynamic>> importPrescription(String prescriptionId) async {
    try {
      final response = await _api.post(
        '/api/v1/medications/medications/import_prescription/',
        data: {'prescription_id': prescriptionId},
      );
      return response.data['medications'] as List;
    } catch (e) {
      throw Exception('Failed to import prescription: $e');
    }
  }

  // ==================== ADHERENCE ====================

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

  /// Get upcoming medications
  /// GET /api/v1/medications/adherence/upcoming/
  Future<List<dynamic>> getUpcomingMedications({
    int hours = 4,
    int? patientId,
  }) async {
    try {
      final queryParams = <String, dynamic>{
        'hours': hours,
        if (patientId != null) 'patient_id': patientId,
      };

      final response = await _api.get(
        '/api/v1/medications/adherence/upcoming/',
        queryParameters: queryParams,
      );
      return response.data as List;
    } catch (e) {
      throw Exception('Failed to load upcoming medications: $e');
    }
  }

  /// Get adherence rate
  /// GET /api/v1/medications/adherence/rate/
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
  /// POST /api/v1/medications/adherence/{id}/mark_taken/
  Future<Map<String, dynamic>> markAdherenceTaken({
    required int adherenceId,
    String? confirmationMethod,
    String? notes,
  }) async {
    try {
      final data = {
        'confirmation_method': confirmationMethod ?? 'app',
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
  /// POST /api/v1/medications/adherence/{id}/mark_skipped/
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

  // ==================== SCHEDULES ====================

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

  /// Create medication schedule
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

  /// Update medication schedule
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

  /// Delete medication schedule
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
