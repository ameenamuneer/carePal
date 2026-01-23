import 'api_service.dart';

/// Complete Family Service - Family Members, Invitations, Notes, Communications, Schedules
/// Maps to backend/family/views.py
class FamilyService {
  final ApiService _api = ApiService();

  // ==================== FAMILY MEMBERS ====================

  /// Get family members
  /// GET /api/v1/family/members/
  Future<Map<String, dynamic>> getFamilyMembers({
    int? patientId,
    String? relationship,
    bool? isActive,
    bool? isPrimaryCaregiver,
    String? search,
    int page = 1,
    int pageSize = 20,
  }) async {
    try {
      final queryParams = <String, dynamic>{
        'page': page,
        'page_size': pageSize,
        if (patientId != null) 'patient': patientId,
        if (relationship != null) 'relationship': relationship,
        if (isActive != null) 'is_active': isActive,
        if (isPrimaryCaregiver != null)
          'is_primary_caregiver': isPrimaryCaregiver,
        if (search != null) 'search': search,
      };

      final response = await _api.get(
        '/api/v1/family/members/',
        queryParameters: queryParams,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to load family members: $e');
    }
  }

  /// Get a single family member
  /// GET /api/v1/family/members/{id}/
  Future<Map<String, dynamic>> getFamilyMember(int id) async {
    try {
      final response = await _api.get('/api/v1/family/members/$id/');
      return response.data;
    } catch (e) {
      throw Exception('Failed to load family member: $e');
    }
  }

  /// Create family member
  /// POST /api/v1/family/members/
  Future<Map<String, dynamic>> createFamilyMember(
    Map<String, dynamic> data,
  ) async {
    try {
      final response = await _api.post('/api/v1/family/members/', data: data);
      return response.data;
    } catch (e) {
      throw Exception('Failed to create family member: $e');
    }
  }

  /// Update family member
  /// PUT /api/v1/family/members/{id}/
  Future<Map<String, dynamic>> updateFamilyMember(
    int id,
    Map<String, dynamic> data,
  ) async {
    try {
      final response = await _api.put(
        '/api/v1/family/members/$id/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to update family member: $e');
    }
  }

  /// Partially update family member
  /// PATCH /api/v1/family/members/{id}/
  Future<Map<String, dynamic>> patchFamilyMember(
    int id,
    Map<String, dynamic> data,
  ) async {
    try {
      final response = await _api.patch(
        '/api/v1/family/members/$id/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to patch family member: $e');
    }
  }

  /// Delete family member
  /// DELETE /api/v1/family/members/{id}/
  Future<void> deleteFamilyMember(int id) async {
    try {
      await _api.delete('/api/v1/family/members/$id/');
    } catch (e) {
      throw Exception('Failed to delete family member: $e');
    }
  }

  /// Get all patients the current family member monitors
  /// GET /api/v1/family/members/my_patients/
  Future<List<dynamic>> getMyPatients() async {
    try {
      final response = await _api.get('/api/v1/family/members/my_patients/');
      return response.data as List;
    } catch (e) {
      throw Exception('Failed to load my patients: $e');
    }
  }

  /// Update family member permissions
  /// POST /api/v1/family/members/{id}/update_permissions/
  Future<Map<String, dynamic>> updateFamilyMemberPermissions(
    int id,
    Map<String, bool> permissions,
  ) async {
    try {
      final response = await _api.post(
        '/api/v1/family/members/$id/update_permissions/',
        data: permissions,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to update permissions: $e');
    }
  }

  /// Record that family member viewed patient data
  /// POST /api/v1/family/members/{id}/record_view/
  Future<Map<String, dynamic>> recordFamilyMemberView(int id) async {
    try {
      final response = await _api.post(
        '/api/v1/family/members/$id/record_view/',
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to record view: $e');
    }
  }

  // ==================== FAMILY INVITATIONS ====================

  /// Get family invitations
  /// GET /api/v1/family/invitations/
  Future<Map<String, dynamic>> getFamilyInvitations({
    int? patientId,
    String? status,
    int page = 1,
    int pageSize = 20,
  }) async {
    try {
      final queryParams = <String, dynamic>{
        'page': page,
        'page_size': pageSize,
        if (patientId != null) 'patient': patientId,
        if (status != null) 'status': status,
      };

      final response = await _api.get(
        '/api/v1/family/invitations/',
        queryParameters: queryParams,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to load family invitations: $e');
    }
  }

  /// Get a single family invitation
  /// GET /api/v1/family/invitations/{id}/
  Future<Map<String, dynamic>> getFamilyInvitation(int id) async {
    try {
      final response = await _api.get('/api/v1/family/invitations/$id/');
      return response.data;
    } catch (e) {
      throw Exception('Failed to load family invitation: $e');
    }
  }

  /// Send invitation to family member
  /// POST /api/v1/family/invitations/send_invitation/
  Future<Map<String, dynamic>> sendFamilyInvitation(
    Map<String, dynamic> data,
  ) async {
    try {
      final response = await _api.post(
        '/api/v1/family/invitations/send_invitation/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to send invitation: $e');
    }
  }

  /// Accept family invitation
  /// POST /api/v1/family/invitations/{id}/accept/
  Future<Map<String, dynamic>> acceptFamilyInvitation(int id) async {
    try {
      final response = await _api.post(
        '/api/v1/family/invitations/$id/accept/',
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to accept invitation: $e');
    }
  }

  /// Cancel family invitation
  /// POST /api/v1/family/invitations/{id}/cancel/
  Future<Map<String, dynamic>> cancelFamilyInvitation(int id) async {
    try {
      final response = await _api.post(
        '/api/v1/family/invitations/$id/cancel/',
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to cancel invitation: $e');
    }
  }

  // ==================== FAMILY NOTES ====================

  /// Get family notes
  /// GET /api/v1/family/notes/
  Future<Map<String, dynamic>> getFamilyNotes({
    int? patientId,
    String? noteType,
    bool? isImportant,
    bool? isPrivate,
    int page = 1,
    int pageSize = 20,
  }) async {
    try {
      final queryParams = <String, dynamic>{
        'page': page,
        'page_size': pageSize,
        if (patientId != null) 'patient': patientId,
        if (noteType != null) 'note_type': noteType,
        if (isImportant != null) 'is_important': isImportant,
        if (isPrivate != null) 'is_private': isPrivate,
      };

      final response = await _api.get(
        '/api/v1/family/notes/',
        queryParameters: queryParams,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to load family notes: $e');
    }
  }

  /// Get a single family note
  /// GET /api/v1/family/notes/{id}/
  Future<Map<String, dynamic>> getFamilyNote(int id) async {
    try {
      final response = await _api.get('/api/v1/family/notes/$id/');
      return response.data;
    } catch (e) {
      throw Exception('Failed to load family note: $e');
    }
  }

  /// Create family note
  /// POST /api/v1/family/notes/
  Future<Map<String, dynamic>> createFamilyNote(
    Map<String, dynamic> data,
  ) async {
    try {
      final response = await _api.post('/api/v1/family/notes/', data: data);
      return response.data;
    } catch (e) {
      throw Exception('Failed to create family note: $e');
    }
  }

  /// Update family note
  /// PUT /api/v1/family/notes/{id}/
  Future<Map<String, dynamic>> updateFamilyNote(
    int id,
    Map<String, dynamic> data,
  ) async {
    try {
      final response = await _api.put('/api/v1/family/notes/$id/', data: data);
      return response.data;
    } catch (e) {
      throw Exception('Failed to update family note: $e');
    }
  }

  /// Delete family note
  /// DELETE /api/v1/family/notes/{id}/
  Future<void> deleteFamilyNote(int id) async {
    try {
      await _api.delete('/api/v1/family/notes/$id/');
    } catch (e) {
      throw Exception('Failed to delete family note: $e');
    }
  }

  // ==================== FAMILY COMMUNICATIONS ====================

  /// Get family communications/messages
  /// GET /api/v1/family/communications/
  Future<Map<String, dynamic>> getFamilyCommunications({
    int? patientId,
    String? messageType,
    int? parentMessageId,
    int page = 1,
    int pageSize = 20,
  }) async {
    try {
      final queryParams = <String, dynamic>{
        'page': page,
        'page_size': pageSize,
        if (patientId != null) 'patient': patientId,
        if (messageType != null) 'message_type': messageType,
        if (parentMessageId != null) 'parent_message': parentMessageId,
      };

      final response = await _api.get(
        '/api/v1/family/communications/',
        queryParameters: queryParams,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to load family communications: $e');
    }
  }

  /// Get a single family communication
  /// GET /api/v1/family/communications/{id}/
  Future<Map<String, dynamic>> getFamilyCommunication(int id) async {
    try {
      final response = await _api.get('/api/v1/family/communications/$id/');
      return response.data;
    } catch (e) {
      throw Exception('Failed to load family communication: $e');
    }
  }

  /// Create family communication
  /// POST /api/v1/family/communications/
  Future<Map<String, dynamic>> createFamilyCommunication(
    Map<String, dynamic> data,
  ) async {
    try {
      final response = await _api.post(
        '/api/v1/family/communications/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to create family communication: $e');
    }
  }

  /// Update family communication
  /// PUT /api/v1/family/communications/{id}/
  Future<Map<String, dynamic>> updateFamilyCommunication(
    int id,
    Map<String, dynamic> data,
  ) async {
    try {
      final response = await _api.put(
        '/api/v1/family/communications/$id/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to update family communication: $e');
    }
  }

  /// Delete family communication
  /// DELETE /api/v1/family/communications/{id}/
  Future<void> deleteFamilyCommunication(int id) async {
    try {
      await _api.delete('/api/v1/family/communications/$id/');
    } catch (e) {
      throw Exception('Failed to delete family communication: $e');
    }
  }

  /// Mark message as read
  /// POST /api/v1/family/communications/{id}/mark_read/
  Future<Map<String, dynamic>> markCommunicationAsRead(int id) async {
    try {
      final response = await _api.post(
        '/api/v1/family/communications/$id/mark_read/',
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to mark communication as read: $e');
    }
  }

  // ==================== CARE SCHEDULES ====================

  /// Get care schedules
  /// GET /api/v1/family/schedules/
  Future<Map<String, dynamic>> getCareSchedules({
    int? patientId,
    int? assignedToId,
    String? status,
    String? scheduleType,
    int page = 1,
    int pageSize = 20,
  }) async {
    try {
      final queryParams = <String, dynamic>{
        'page': page,
        'page_size': pageSize,
        if (patientId != null) 'patient': patientId,
        if (assignedToId != null) 'assigned_to': assignedToId,
        if (status != null) 'status': status,
        if (scheduleType != null) 'schedule_type': scheduleType,
      };

      final response = await _api.get(
        '/api/v1/family/schedules/',
        queryParameters: queryParams,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to load care schedules: $e');
    }
  }

  /// Get a single care schedule
  /// GET /api/v1/family/schedules/{id}/
  Future<Map<String, dynamic>> getCareSchedule(int id) async {
    try {
      final response = await _api.get('/api/v1/family/schedules/$id/');
      return response.data;
    } catch (e) {
      throw Exception('Failed to load care schedule: $e');
    }
  }

  /// Create care schedule
  /// POST /api/v1/family/schedules/
  Future<Map<String, dynamic>> createCareSchedule(
    Map<String, dynamic> data,
  ) async {
    try {
      final response = await _api.post('/api/v1/family/schedules/', data: data);
      return response.data;
    } catch (e) {
      throw Exception('Failed to create care schedule: $e');
    }
  }

  /// Update care schedule
  /// PUT /api/v1/family/schedules/{id}/
  Future<Map<String, dynamic>> updateCareSchedule(
    int id,
    Map<String, dynamic> data,
  ) async {
    try {
      final response = await _api.put(
        '/api/v1/family/schedules/$id/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to update care schedule: $e');
    }
  }

  /// Delete care schedule
  /// DELETE /api/v1/family/schedules/{id}/
  Future<void> deleteCareSchedule(int id) async {
    try {
      await _api.delete('/api/v1/family/schedules/$id/');
    } catch (e) {
      throw Exception('Failed to delete care schedule: $e');
    }
  }

  /// Mark schedule as complete
  /// POST /api/v1/family/schedules/{id}/mark_complete/
  Future<Map<String, dynamic>> markScheduleComplete(
    int id, {
    String? completionNotes,
  }) async {
    try {
      final data = {
        if (completionNotes != null) 'completion_notes': completionNotes,
      };

      final response = await _api.post(
        '/api/v1/family/schedules/$id/mark_complete/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to mark schedule as complete: $e');
    }
  }

  /// Get upcoming schedules
  /// GET /api/v1/family/schedules/upcoming/
  Future<List<dynamic>> getUpcomingSchedules({
    int? patientId,
    int days = 7,
  }) async {
    try {
      final queryParams = <String, dynamic>{
        'days': days,
        if (patientId != null) 'patient_id': patientId,
      };

      final response = await _api.get(
        '/api/v1/family/schedules/upcoming/',
        queryParameters: queryParams,
      );
      return response.data as List;
    } catch (e) {
      throw Exception('Failed to load upcoming schedules: $e');
    }
  }

  /// Get schedules assigned to current user
  /// GET /api/v1/family/schedules/my_tasks/
  Future<List<dynamic>> getMyTasks() async {
    try {
      final response = await _api.get('/api/v1/family/schedules/my_tasks/');
      return response.data as List;
    } catch (e) {
      throw Exception('Failed to load my tasks: $e');
    }
  }

  // ==================== FAMILY DASHBOARD ====================

  /// Get family dashboard for a patient
  /// GET /api/v1/family/dashboard/
  Future<Map<String, dynamic>> getFamilyDashboard({
    required int patientId,
  }) async {
    try {
      final queryParams = {'patient_id': patientId};

      final response = await _api.get(
        '/api/v1/family/dashboard/',
        queryParameters: queryParams,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to load family dashboard: $e');
    }
  }

  // ==================== ACTIVITY LOGS ====================

  /// Get family activity logs
  /// GET /api/v1/family/activity-logs/
  Future<Map<String, dynamic>> getActivityLogs({
    int? familyMemberId,
    int? patientId,
    String? action,
    int page = 1,
    int pageSize = 20,
  }) async {
    try {
      final queryParams = <String, dynamic>{
        'page': page,
        'page_size': pageSize,
        if (familyMemberId != null) 'family_member': familyMemberId,
        if (patientId != null) 'patient': patientId,
        if (action != null) 'action': action,
      };

      final response = await _api.get(
        '/api/v1/family/activity-logs/',
        queryParameters: queryParams,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to load activity logs: $e');
    }
  }

  /// Get a single activity log
  /// GET /api/v1/family/activity-logs/{id}/
  Future<Map<String, dynamic>> getActivityLog(int id) async {
    try {
      final response = await _api.get('/api/v1/family/activity-logs/$id/');
      return response.data;
    } catch (e) {
      throw Exception('Failed to load activity log: $e');
    }
  }
}
