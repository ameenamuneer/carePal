import 'package:flutter/foundation.dart';
import '../services/dashboard_service.dart';

class DashboardProvider extends ChangeNotifier {
  final DashboardService _service = DashboardService();

  Map<String, dynamic>? _data;
  bool _isLoading = false;
  String? _error;
  int? _lastPatientId;
  DateTime? _lastFetched;

  Map<String, dynamic>? get data => _data;
  bool get isLoading => _isLoading;
  String? get error => _error;

  bool get hasData => _data != null;

  /// True when data is older than 60 seconds
  bool get isStale =>
      _lastFetched == null ||
      DateTime.now().difference(_lastFetched!).inSeconds > 60;

  Future<void> load({
    required int patientId,
    required bool isDoctor,
    bool force = false,
  }) async {
    // Skip if already loading or data is fresh for this patient
    if (_isLoading) return;
    if (!force && _lastPatientId == patientId && !isStale) return;

    _isLoading = true;
    _error = null;
    if (_lastPatientId != patientId) _data = null; // clear stale patient data
    notifyListeners();

    try {
      final result = isDoctor
          ? await _service.getDoctorDashboard(patientId)
          : await _service.getFamilyDashboard(patientId);
      _data = result;
      _lastPatientId = patientId;
      _lastFetched = DateTime.now();
    } catch (e) {
      _error = e.toString();
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  void clear() {
    _data = null;
    _isLoading = false;
    _error = null;
    _lastPatientId = null;
    _lastFetched = null;
    notifyListeners();
  }

  // ── Typed accessors ──────────────────────────────────────────────────────

  Map<String, dynamic> get medications =>
      Map<String, dynamic>.from(_data?['medications'] as Map? ?? {});

  Map<String, dynamic> get nutrition =>
      Map<String, dynamic>.from(_data?['nutrition'] as Map? ?? {});

  Map<String, dynamic>? get mood =>
      _data?['mood'] != null ? Map<String, dynamic>.from(_data!['mood'] as Map) : null;

  List<Map<String, dynamic>> get vitals =>
      (_data?['vitals'] as List? ?? []).cast<Map<String, dynamic>>();

  List<Map<String, dynamic>> get alerts =>
      (_data?['alerts'] as List? ?? []).cast<Map<String, dynamic>>();

  Map<String, dynamic> get alertCounts =>
      Map<String, dynamic>.from(_data?['alert_counts'] as Map? ?? {});

  List<Map<String, dynamic>> get adherence7day =>
      (medications['adherence_7day'] as List? ?? []).cast<Map<String, dynamic>>();

  List<Map<String, dynamic>> get nutrition7day =>
      (nutrition['nutrition_7day'] as List? ?? []).cast<Map<String, dynamic>>();

  List<Map<String, dynamic>> get mealsToday =>
      (nutrition['meals_today'] as List? ?? []).cast<Map<String, dynamic>>();

  List<Map<String, dynamic>> get missedToday =>
      (medications['missed_today'] as List? ?? []).cast<Map<String, dynamic>>();

  List<Map<String, dynamic>> get recentActivity =>
      (_data?['recent_activity'] as List? ?? []).cast<Map<String, dynamic>>();

  /// AI-generated natural language insights for each family dashboard card.
  /// Keys: medications, nutrition, mood, vitals, activity
  Map<String, dynamic> get aiInsights =>
      Map<String, dynamic>.from(_data?['ai_insights'] as Map? ?? {});

  String? aiInsight(String card) {
    final v = aiInsights[card];
    return (v is String && v.isNotEmpty) ? v : null;
  }
}
