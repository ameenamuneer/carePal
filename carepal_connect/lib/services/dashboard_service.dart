import 'api_service.dart';

class DashboardService {
  final ApiService _api = ApiService();

  Future<Map<String, dynamic>> getFamilyDashboard(int patientId) async {
    final resp = await _api.get(
      '/api/v1/analytics/dashboard/family/',
      queryParameters: {'patient_id': patientId},
    );
    return Map<String, dynamic>.from(resp.data as Map);
  }

  Future<Map<String, dynamic>> getDoctorDashboard(int patientId) async {
    final resp = await _api.get(
      '/api/v1/analytics/dashboard/doctor/',
      queryParameters: {'patient_id': patientId},
    );
    return Map<String, dynamic>.from(resp.data as Map);
  }
}
