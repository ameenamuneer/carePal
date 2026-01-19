import 'api_service.dart';

class EmergencyService {
  final ApiService _apiService = ApiService();

  Future<List<dynamic>> getFamilyMembers(int patientId) async {
    try {
      final response = await _apiService.get(
        '/api/v1/family/members/?patient_id=$patientId',
      );
      return response.data['results'] ?? [];
    } catch (e) {
      throw Exception('Failed to get family members: $e');
    }
  }

  Future<void> triggerEmergencyCall(int patientId, String reason) async {
    try {
      await _apiService.post(
        '/api/v1/family/emergency-call/',
        data: {'patient_id': patientId, 'reason': reason},
      );
    } catch (e) {
      throw Exception('Failed to trigger emergency call: $e');
    }
  }
}
