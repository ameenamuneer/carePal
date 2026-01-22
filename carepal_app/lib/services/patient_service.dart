import 'api_service.dart';

/// Patient Service - Complete implementation
/// Maps to backend/patients/views.py endpoints
class PatientService {
  final ApiService _api = ApiService();

  // ==================== PATIENT PROFILE CRUD ====================

  /// Get list of patient profiles
  /// GET /api/v1/patients/profiles/
  Future<Map<String, dynamic>> getPatientProfiles({
    String? gender,
    String? bloodGroup,
    String? preferredLanguage,
    String? city,
    String? state,
    bool? isActive,
    String? search,
    int page = 1,
    int pageSize = 20,
  }) async {
    try {
      final queryParams = <String, dynamic>{
        'page': page,
        'page_size': pageSize,
        if (gender != null) 'gender': gender,
        if (bloodGroup != null) 'blood_group': bloodGroup,
        if (preferredLanguage != null) 'preferred_language': preferredLanguage,
        if (city != null) 'city': city,
        if (state != null) 'state': state,
        if (isActive != null) 'is_active': isActive,
        if (search != null) 'search': search,
      };

      final response = await _api.get(
        '/api/v1/patients/profiles/',
        queryParameters: queryParams,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to load patient profiles: $e');
    }
  }

  /// Get a single patient profile
  /// GET /api/v1/patients/profiles/{id}/
  Future<Map<String, dynamic>> getPatientProfile(int id) async {
    try {
      final response = await _api.get('/api/v1/patients/profiles/$id/');
      return response.data;
    } catch (e) {
      throw Exception('Failed to load patient profile: $e');
    }
  }

  /// Create a new patient profile
  /// POST /api/v1/patients/profiles/
  Future<Map<String, dynamic>> createPatientProfile(
    Map<String, dynamic> data,
  ) async {
    try {
      final response = await _api.post(
        '/api/v1/patients/profiles/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to create patient profile: $e');
    }
  }

  /// Update a patient profile
  /// PUT /api/v1/patients/profiles/{id}/
  Future<Map<String, dynamic>> updatePatientProfile(
    int id,
    Map<String, dynamic> data,
  ) async {
    try {
      final response = await _api.put(
        '/api/v1/patients/profiles/$id/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to update patient profile: $e');
    }
  }

  /// Partially update a patient profile
  /// PATCH /api/v1/patients/profiles/{id}/
  Future<Map<String, dynamic>> patchPatientProfile(
    int id,
    Map<String, dynamic> data,
  ) async {
    try {
      final response = await _api.patch(
        '/api/v1/patients/profiles/$id/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to patch patient profile: $e');
    }
  }

  /// Deactivate a patient profile (soft delete)
  /// DELETE /api/v1/patients/profiles/{id}/
  Future<void> deletePatientProfile(int id) async {
    try {
      await _api.delete('/api/v1/patients/profiles/$id/');
    } catch (e) {
      throw Exception('Failed to delete patient profile: $e');
    }
  }

  // ==================== PATIENT PROFILE ACTIONS ====================

  /// Get health summary for a patient
  /// GET /api/v1/patients/profiles/{id}/health_summary/
  Future<Map<String, dynamic>> getHealthSummary(int id) async {
    try {
      final response = await _api.get(
        '/api/v1/patients/profiles/$id/health_summary/',
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to load health summary: $e');
    }
  }

  /// Get current user's patient profile
  /// GET /api/v1/patients/profiles/my_profile/
  Future<Map<String, dynamic>> getMyProfile() async {
    try {
      final response = await _api.get('/api/v1/patients/profiles/my_profile/');
      return response.data;
    } catch (e) {
      throw Exception('Failed to load my profile: $e');
    }
  }

  /// Add a health condition to patient
  /// POST /api/v1/patients/profiles/{id}/add_health_condition/
  Future<Map<String, dynamic>> addHealthCondition(
    int id, {
    required String condition,
  }) async {
    try {
      final data = {'condition': condition};

      final response = await _api.post(
        '/api/v1/patients/profiles/$id/add_health_condition/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to add health condition: $e');
    }
  }

  /// Remove a health condition from patient
  /// POST /api/v1/patients/profiles/{id}/remove_health_condition/
  Future<Map<String, dynamic>> removeHealthCondition(
    int id, {
    required String condition,
  }) async {
    try {
      final data = {'condition': condition};

      final response = await _api.post(
        '/api/v1/patients/profiles/$id/remove_health_condition/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to remove health condition: $e');
    }
  }

  // ==================== EMERGENCY CONTACTS CRUD ====================

  /// Get list of emergency contacts
  /// GET /api/v1/patients/emergency-contacts/
  Future<Map<String, dynamic>> getEmergencyContacts({
    int? patientId,
    int page = 1,
    int pageSize = 20,
  }) async {
    try {
      final queryParams = <String, dynamic>{
        'page': page,
        'page_size': pageSize,
        if (patientId != null) 'patient': patientId,
      };

      final response = await _api.get(
        '/api/v1/patients/emergency-contacts/',
        queryParameters: queryParams,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to load emergency contacts: $e');
    }
  }

  /// Get a single emergency contact
  /// GET /api/v1/patients/emergency-contacts/{id}/
  Future<Map<String, dynamic>> getEmergencyContact(int id) async {
    try {
      final response = await _api.get(
        '/api/v1/patients/emergency-contacts/$id/',
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to load emergency contact: $e');
    }
  }

  /// Create a new emergency contact
  /// POST /api/v1/patients/emergency-contacts/
  Future<Map<String, dynamic>> createEmergencyContact({
    required int patientId,
    required String name,
    required String relationship,
    required String phoneNumber,
    String? alternatePhone,
    String? email,
    bool isPrimary = false,
    int priorityOrder = 1,
    String? notes,
  }) async {
    try {
      final data = {
        'patient_id': patientId,
        'name': name,
        'relationship': relationship,
        'phone_number': phoneNumber,
        if (alternatePhone != null) 'alternate_phone': alternatePhone,
        if (email != null) 'email': email,
        'is_primary': isPrimary,
        'priority_order': priorityOrder,
        if (notes != null) 'notes': notes,
      };

      final response = await _api.post(
        '/api/v1/patients/emergency-contacts/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to create emergency contact: $e');
    }
  }

  /// Update an emergency contact
  /// PUT /api/v1/patients/emergency-contacts/{id}/
  Future<Map<String, dynamic>> updateEmergencyContact(
    int id,
    Map<String, dynamic> data,
  ) async {
    try {
      final response = await _api.put(
        '/api/v1/patients/emergency-contacts/$id/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to update emergency contact: $e');
    }
  }

  /// Partially update an emergency contact
  /// PATCH /api/v1/patients/emergency-contacts/{id}/
  Future<Map<String, dynamic>> patchEmergencyContact(
    int id,
    Map<String, dynamic> data,
  ) async {
    try {
      final response = await _api.patch(
        '/api/v1/patients/emergency-contacts/$id/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to patch emergency contact: $e');
    }
  }

  /// Delete an emergency contact (soft delete)
  /// DELETE /api/v1/patients/emergency-contacts/{id}/
  Future<Map<String, dynamic>> deleteEmergencyContact(int id) async {
    try {
      final response = await _api.delete(
        '/api/v1/patients/emergency-contacts/$id/',
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to delete emergency contact: $e');
    }
  }

  // ==================== HEALTH CONDITIONS CATALOG ====================

  /// Get health conditions catalog
  /// GET /api/v1/patients/health-conditions/
  Future<Map<String, dynamic>> getHealthConditions({
    String? category,
    String? search,
    int page = 1,
    int pageSize = 50,
  }) async {
    try {
      final queryParams = <String, dynamic>{
        'page': page,
        'page_size': pageSize,
        if (category != null) 'category': category,
        if (search != null) 'search': search,
      };

      final response = await _api.get(
        '/api/v1/patients/health-conditions/',
        queryParameters: queryParams,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to load health conditions: $e');
    }
  }

  /// Get a single health condition
  /// GET /api/v1/patients/health-conditions/{id}/
  Future<Map<String, dynamic>> getHealthCondition(int id) async {
    try {
      final response = await _api.get(
        '/api/v1/patients/health-conditions/$id/',
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to load health condition: $e');
    }
  }

  /// Get health conditions grouped by category
  /// GET /api/v1/patients/health-conditions/by_category/
  Future<Map<String, dynamic>> getHealthConditionsByCategory() async {
    try {
      final response = await _api.get(
        '/api/v1/patients/health-conditions/by_category/',
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to load health conditions by category: $e');
    }
  }
}
