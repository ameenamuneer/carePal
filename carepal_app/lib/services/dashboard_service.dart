import 'api_service.dart';
import '../models/dashboard_data.dart';

class DashboardService {
  final ApiService _api = ApiService();

  // Get dashboard overview
  Future<DashboardData> getDashboard() async {
    try {
      final response = await _api.get('/api/v1/analytics/dashboard/patient/');
      return DashboardData.fromJson(response.data);
    } catch (e) {
      throw Exception('Failed to load dashboard: $e');
    }
  }

  // Refresh dashboard data
  Future<DashboardData> refresh() async {
    return getDashboard();
  }
}
