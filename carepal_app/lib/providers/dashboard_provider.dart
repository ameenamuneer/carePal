import 'package:flutter/material.dart';
import '../models/dashboard_data.dart';
import '../services/dashboard_service.dart';

class DashboardProvider with ChangeNotifier {
  final DashboardService _service = DashboardService();

  DashboardData? _dashboardData;
  bool _isLoading = false;
  String? _error;

  DashboardData? get dashboardData => _dashboardData;
  bool get isLoading => _isLoading;
  String? get error => _error;

  // Convenience getters
  HealthScore? get healthScore => _dashboardData?.healthScore;
  Map<String, VitalSummary>? get vitalsSummary => _dashboardData?.vitalsSummary;
  MedicationAdherenceSummary? get medicationAdherence =>
      _dashboardData?.medicationAdherence;
  List<Insight> get insights => _dashboardData?.insights ?? [];
  List<Recommendation> get recommendations =>
      _dashboardData?.recommendations ?? [];

  // Load dashboard
  Future<void> loadDashboard() async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      _dashboardData = await _service.getDashboard();
    } catch (e) {
      _error = e.toString();
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  // Refresh dashboard
  Future<void> refresh() async {
    await loadDashboard();
  }

  // Get vital summary by code
  VitalSummary? getVitalSummary(String vitalCode) {
    return _dashboardData?.vitalsSummary[vitalCode];
  }

  // Clear error
  void clearError() {
    _error = null;
    notifyListeners();
  }
}
