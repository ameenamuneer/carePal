// lib/providers/dashboard_provider.dart
// FIXED VERSION - Prevents setState during build

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
    // CRITICAL FIX: Only set loading if not already loading
    if (_isLoading) return;

    _isLoading = true;
    _error = null;

    // CRITICAL FIX: Use post-frame callback to avoid build-time setState
    WidgetsBinding.instance.addPostFrameCallback((_) {
      notifyListeners();
    });

    try {
      _dashboardData = await _service.getDashboard();
      _error = null;
    } catch (e) {
      _error = e.toString();
      debugPrint('Dashboard load error: $e');
    } finally {
      _isLoading = false;

      // CRITICAL FIX: Use post-frame callback for final notification
      WidgetsBinding.instance.addPostFrameCallback((_) {
        notifyListeners();
      });
    }
  }

  // Refresh dashboard - silent version without notifying during load
  Future<void> refresh() async {
    await loadDashboard();
  }

  // SAFE refresh that can be called during build
  void requestRefresh() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      loadDashboard();
    });
  }

  // Get vital summary by code
  VitalSummary? getVitalSummary(String vitalCode) {
    return _dashboardData?.vitalsSummary[vitalCode];
  }

  // Clear error
  void clearError() {
    _error = null;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      notifyListeners();
    });
  }
}
