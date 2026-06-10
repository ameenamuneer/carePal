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

  // Calendar: { "YYYY-MM-DD": { total, taken, missed, skipped, scheduled } }
  Map<String, Map<String, int>> _calendarData = {};
  // Cached day schedules for the popup: { "YYYY-MM-DD": [MedicationSchedule] }
  final Map<String, List<MedicationSchedule>> _dayScheduleCache = {};
  bool _isLoadingCalendar = false;

  List<MedicationSchedule> get todaysSchedule => _todaysSchedule;
  List<MedicationAdherence> get adherenceHistory => _adherenceHistory;
  List<Medication> get medications => _medications;
  double get adherenceRate => _adherenceRate;
  bool get isLoading => _isLoading;
  bool get isLoadingHistory => _isLoadingHistory;
  String? get error => _error;
  int? get patientId => _patientId;
  bool get hasMoreHistory => _hasMoreHistory;
  Map<String, Map<String, int>> get calendarData => _calendarData;
  bool get isLoadingCalendar => _isLoadingCalendar;

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
      loadCalendarSummary(),
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

  Future<void> loadCalendarSummary() async {
    if (_patientId == null) return;
    _isLoadingCalendar = true;
    _safeNotify();
    try {
      final raw = await _service.getCalendarSummary(patientId: _patientId!);
      _calendarData = raw.map((k, v) {
        final m = Map<String, dynamic>.from(v as Map);
        return MapEntry(k, {
          'total': (m['total'] as num).toInt(),
          'taken': (m['taken'] as num).toInt(),
          'missed': (m['missed'] as num).toInt(),
          'skipped': (m['skipped'] as num).toInt(),
          'scheduled': (m['scheduled'] as num).toInt(),
        });
      });
    } catch (e) {
      debugPrint('Error loading calendar summary: $e');
    } finally {
      _isLoadingCalendar = false;
      _safeNotify();
    }
  }

  /// Fetch (and cache) the schedule for a specific date for the day popup.
  Future<List<MedicationSchedule>> loadDaySchedule(DateTime day) async {
    if (_patientId == null) return [];
    final key = '${day.year}-${day.month.toString().padLeft(2, '0')}-${day.day.toString().padLeft(2, '0')}';
    if (_dayScheduleCache.containsKey(key)) return _dayScheduleCache[key]!;
    try {
      final results = await _service.getTodaysSchedule(patientId: _patientId, date: key);
      final list = results
          .map((i) => MedicationSchedule.fromJson(i as Map<String, dynamic>))
          .toList();
      _dayScheduleCache[key] = list;
      return list;
    } catch (e) {
      return [];
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
      _dayScheduleCache.clear();
      await Future.wait([loadTodaysSchedule(), loadCalendarSummary()]);
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
      _dayScheduleCache.clear();
      await Future.wait([loadTodaysSchedule(), loadCalendarSummary()]);
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
    _calendarData = {};
    _dayScheduleCache.clear();
    _isLoadingCalendar = false;
    notifyListeners();
  }
}
