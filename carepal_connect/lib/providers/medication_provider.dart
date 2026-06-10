import 'package:flutter/material.dart';
import '../models/medication.dart';
import '../services/medication_service.dart';

class MedicationProvider extends ChangeNotifier {
  final MedicationService _service = MedicationService();

  List<MedicationSchedule> _todaysSchedule = [];
  List<MedicationAdherence> _adherenceHistory = [];
  List<Medication> _medications = [];
  double _adherenceRate = 0.0;
  bool _isLoading = false;
  bool _isLoadingHistory = false;
  String? _error;
  int? _patientId;
  bool _hasMoreHistory = true;
  int _historyPage = 1;

  List<MedicationSchedule> get todaysSchedule => _todaysSchedule;
  List<MedicationAdherence> get adherenceHistory => _adherenceHistory;
  List<Medication> get medications => _medications;
  double get adherenceRate => _adherenceRate;
  bool get isLoading => _isLoading;
  bool get isLoadingHistory => _isLoadingHistory;
  String? get error => _error;
  int? get patientId => _patientId;
  bool get hasMoreHistory => _hasMoreHistory;

  void _safeNotify() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      notifyListeners();
    });
  }

  /// Call this when active patient changes; reloads if patient actually changed.
  void setPatientAndReload(int? patientId) {
    if (_patientId == patientId) return;
    _patientId = patientId;
    if (patientId != null) {
      loadAll();
    } else {
      clear();
    }
  }

  /// Load everything in parallel.
  Future<void> loadAll() async {
    await Future.wait([
      loadTodaysSchedule(),
      loadMedications(),
      loadAdherenceRate(),
      loadHistory(reset: true),
    ]);
  }

  Future<void> loadTodaysSchedule({String? date}) async {
    _isLoading = true;
    _error = null;
    _safeNotify();

    try {
      final results = await _service.getTodaysSchedule(
        patientId: _patientId,
        date: date,
      );
      _todaysSchedule = results
          .map((i) => MedicationSchedule.fromJson(i as Map<String, dynamic>))
          .toList();
      _error = null;
    } catch (e) {
      _error = e.toString();
      debugPrint('Error loading schedule: $e');
    } finally {
      _isLoading = false;
      _safeNotify();
    }
  }

  Future<void> loadMedications() async {
    try {
      final response = await _service.getMedications(
        status: 'ACTIVE',
        patientId: _patientId,
      );
      if (response['results'] != null) {
        _medications = (response['results'] as List)
            .map((i) => Medication.fromJson(i as Map<String, dynamic>))
            .toList();
      }
      _safeNotify();
    } catch (e) {
      debugPrint('Error loading medications: $e');
    }
  }

  Future<void> loadAdherenceRate({int days = 7}) async {
    try {
      final result =
          await _service.getAdherenceRate(days: days, patientId: _patientId);
      if (result['adherence_rate'] != null) {
        _adherenceRate = (result['adherence_rate'] as num).toDouble();
      }
      _safeNotify();
    } catch (e) {
      debugPrint('Error loading adherence rate: $e');
    }
  }

  Future<void> loadHistory({bool reset = true}) async {
    if (reset) {
      _historyPage = 1;
      _hasMoreHistory = true;
      _adherenceHistory = [];
    } else if (!_hasMoreHistory) {
      return;
    }

    _isLoadingHistory = true;
    _safeNotify();

    try {
      final response = await _service.getAdherenceHistory(
        patientId: _patientId,
        page: _historyPage,
        pageSize: 20,
      );

      final results = response['results'] as List? ?? [];
      final newEntries = results
          .map((i) => MedicationAdherence.fromJson(i as Map<String, dynamic>))
          .toList();

      _hasMoreHistory = response['next'] != null;
      _historyPage++;

      if (reset) {
        _adherenceHistory = newEntries;
      } else {
        _adherenceHistory = [..._adherenceHistory, ...newEntries];
      }
    } catch (e) {
      debugPrint('Error loading adherence history: $e');
    } finally {
      _isLoadingHistory = false;
      _safeNotify();
    }
  }

  Future<void> loadMoreHistory() => loadHistory(reset: false);

  /// Mark a scheduled adherence record as TAKEN.
  Future<bool> markTaken(int adherenceId, {String? notes}) async {
    try {
      await _service.markAdherenceTaken(
        adherenceId: adherenceId,
        notes: notes,
        confirmationMethod: 'MANUAL',
      );
      // Refresh local data
      await loadTodaysSchedule();
      await loadHistory(reset: true);
      return true;
    } catch (e) {
      _error = e.toString();
      _safeNotify();
      return false;
    }
  }

  /// Mark a scheduled adherence record as SKIPPED.
  Future<bool> skipMedication(int adherenceId, String reason) async {
    try {
      await _service.markAdherenceSkipped(
        adherenceId: adherenceId,
        reason: reason,
      );
      await loadTodaysSchedule();
      await loadHistory(reset: true);
      return true;
    } catch (e) {
      _error = e.toString();
      _safeNotify();
      return false;
    }
  }

  /// Delete a medication and refresh data.
  Future<bool> deleteMedication(int medicationId) async {
    try {
      await _service.deleteMedication(medicationId);
      await loadAll();
      return true;
    } catch (e) {
      _error = e.toString();
      _safeNotify();
      return false;
    }
  }

  /// Wipe all state — called on logout or patient change.
  void clear() {
    _todaysSchedule = [];
    _adherenceHistory = [];
    _medications = [];
    _adherenceRate = 0.0;
    _isLoading = false;
    _isLoadingHistory = false;
    _error = null;
    _patientId = null;
    _hasMoreHistory = true;
    _historyPage = 1;
    notifyListeners();
  }
}
