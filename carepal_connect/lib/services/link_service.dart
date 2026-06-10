import '../models/patient_link.dart';
import 'api_service.dart';

class LinkService {
  final ApiService _api = ApiService();

  // ==================== DOCTOR ====================

  /// POST /api/v1/auth/clinical-relationships/
  Future<ClinicalRelationship> linkPatientAsDoctor(
      int patientId, String role) async {
    try {
      final response = await _api.post(
        '/api/v1/auth/clinical-relationships/',
        data: {'patient': patientId, 'role': role},
      );
      return ClinicalRelationship.fromJson(
          response.data as Map<String, dynamic>);
    } catch (e) {
      throw Exception('Failed to link patient: $e');
    }
  }

  /// GET /api/v1/auth/clinical-relationships/my-patients/
  Future<List<ClinicalRelationship>> getMyPatients() async {
    try {
      final response =
          await _api.get('/api/v1/auth/clinical-relationships/my-patients/');
      final list = response.data as List;
      return list
          .map((e) =>
              ClinicalRelationship.fromJson(e as Map<String, dynamic>))
          .toList();
    } catch (e) {
      throw Exception('Failed to load patients: $e');
    }
  }

  /// DELETE /api/v1/auth/clinical-relationships/{id}/
  Future<void> unlinkPatient(int relationshipId) async {
    try {
      await _api.delete(
          '/api/v1/auth/clinical-relationships/$relationshipId/');
    } catch (e) {
      throw Exception('Failed to unlink patient: $e');
    }
  }

  // ==================== FAMILY ====================

  /// POST /api/v1/family/members/
  Future<FamilyMemberLink> linkPatientAsFamily(
      int userId, int patientId, String relationship) async {
    try {
      final response = await _api.post(
        '/api/v1/family/members/',
        data: {
          'user': userId,
          'patient': patientId,
          'relationship': relationship,
        },
      );
      return FamilyMemberLink.fromJson(response.data as Map<String, dynamic>);
    } catch (e) {
      throw Exception('Failed to link patient: $e');
    }
  }

  /// GET /api/v1/family/members/
  Future<List<FamilyMemberLink>> getMyFamilyLinks() async {
    try {
      final response = await _api.get('/api/v1/family/members/');
      final data = response.data;
      final list = data is Map ? (data['results'] ?? data) : data;
      return (list as List)
          .map((e) =>
              FamilyMemberLink.fromJson(e as Map<String, dynamic>))
          .toList();
    } catch (e) {
      throw Exception('Failed to load family links: $e');
    }
  }

  /// DELETE /api/v1/family/members/{id}/
  Future<void> unlinkFamilyPatient(int memberId) async {
    try {
      await _api.delete('/api/v1/family/members/$memberId/');
    } catch (e) {
      throw Exception('Failed to unlink patient: $e');
    }
  }
}
