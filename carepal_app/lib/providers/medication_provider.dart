// lib/providers/medication_provider.dart
// CRITICAL FIX - Prevents setState during build

import 'package:flutter/material.dart';
import '../models/medication.dart';
import '../services/medication_service.dart';

class MedicationProvider with ChangeNotifier {
  final MedicationService _service = MedicationService();

  List<MedicationSchedule> _todaysSchedule = [];
  List<Medication> _medications = [];
  List<MedicationAdherence> _adherenceHistory = [];
  double _adherenceRate = 0.0;
  bool _isLoading = false;
  String? _error;

  List<MedicationSchedule> get todaysSchedule => _todaysSchedule;
  List<Medication> get medications => _medications;
  List<MedicationAdherence> get adherenceHistory => _adherenceHistory;
  double get adherenceRate => _adherenceRate;
  bool get isLoading => _isLoading;
  String? get error => _error;

  // CRITICAL FIX: Safe notification helper
  void _safeNotify() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      notifyListeners();
    });
  }

  // Load today's schedule
  Future<void> loadTodaysSchedule() async {
    // CRITICAL FIX: Only set loading if not already loading
    if (_isLoading) return;

    _isLoading = true;
    _error = null;
    _safeNotify(); // FIXED: Use post-frame callback

    try {
      final results = await _service.getTodaysSchedule();
      _todaysSchedule = (results)
          .map((i) => MedicationSchedule.fromJson(i))
          .toList();
      _error = null;
    } catch (e) {
      _error = e.toString();
      debugPrint('Error loading today\'s schedule: $e');
    } finally {
      _isLoading = false;
      _safeNotify(); // FIXED: Use post-frame callback
    }
  }

  // Load all medications
  Future<void> loadMedications({String? status}) async {
    _isLoading = true;
    _error = null;
    _safeNotify(); // FIXED: Use post-frame callback

    try {
      final response = await _service.getMedications(status: status);
      if (response['results'] != null) {
        _medications = (response['results'] as List)
            .map((i) => Medication.fromJson(i))
            .toList();
      }
      _error = null;
    } catch (e) {
      _error = e.toString();
      debugPrint('Error loading medications: $e');
    } finally {
      _isLoading = false;
      _safeNotify(); // FIXED: Use post-frame callback
    }
  }

  // Log medication as taken
  Future<bool> markAsTaken(int adherenceId, {String? notes}) async {
    _isLoading = true;
    _error = null;
    _safeNotify(); // FIXED: Use post-frame callback

    try {
      await _service.markAdherenceTaken(adherenceId: adherenceId, notes: notes);

      // Update local schedule
      final index = _todaysSchedule.indexWhere((s) => s.id == adherenceId);
      if (index != -1) {
        _todaysSchedule[index] = MedicationSchedule(
          id: _todaysSchedule[index].id,
          medication: _todaysSchedule[index].medication,
          scheduledTime: _todaysSchedule[index].scheduledTime,
          status: 'TAKEN',
          takenAt: DateTime.now(),
          notes: notes,
        );
      }

      _error = null;
      _safeNotify(); // FIXED: Use post-frame callback
      return true;
    } catch (e) {
      _error = e.toString();
      _safeNotify(); // FIXED: Use post-frame callback
      return false;
    } finally {
      _isLoading = false;
      _safeNotify(); // FIXED: Use post-frame callback
    }
  }

  // Skip medication
  Future<bool> skipMedication(int adherenceId, String reason) async {
    _isLoading = true;
    _error = null;
    _safeNotify(); // FIXED: Use post-frame callback

    try {
      await _service.markAdherenceSkipped(
        adherenceId: adherenceId,
        reason: reason,
      );

      // Update local schedule
      final index = _todaysSchedule.indexWhere((s) => s.id == adherenceId);
      if (index != -1) {
        _todaysSchedule[index] = MedicationSchedule(
          id: _todaysSchedule[index].id,
          medication: _todaysSchedule[index].medication,
          scheduledTime: _todaysSchedule[index].scheduledTime,
          status: 'SKIPPED',
          notes: reason,
        );
      }

      _error = null;
      _safeNotify(); // FIXED: Use post-frame callback
      return true;
    } catch (e) {
      _error = e.toString();
      _safeNotify(); // FIXED: Use post-frame callback
      return false;
    } finally {
      _isLoading = false;
      _safeNotify(); // FIXED: Use post-frame callback
    }
  }

  // Load adherence history
  Future<void> loadAdherenceHistory({int? medicationId, int days = 30}) async {
    try {
      final response = await _service.getAdherenceHistory(
        medicationId: medicationId,
      );

      if (response['results'] != null) {
        _adherenceHistory = (response['results'] as List)
            .map((i) => MedicationAdherence.fromJson(i))
            .toList();
      }

      _safeNotify(); // FIXED: Use post-frame callback
    } catch (e) {
      _error = e.toString();
      _safeNotify(); // FIXED: Use post-frame callback
    }
  }

  // Load adherence rate
  Future<void> loadAdherenceRate({int days = 7}) async {
    try {
      final result = await _service.getAdherenceRate(days: days);
      if (result['adherence_rate'] != null) {
        _adherenceRate = (result['adherence_rate'] as num).toDouble();
      }
      _safeNotify(); // FIXED: Use post-frame callback
    } catch (e) {
      _error = e.toString();
      debugPrint('Error loading adherence rate: $e');
      _safeNotify(); // FIXED: Use post-frame callback
    }
  }

  // Get scheduled medications (not taken yet)
  List<MedicationSchedule> get scheduledMedications {
    return _todaysSchedule.where((s) => s.isScheduled).toList();
  }

  // Get taken medications
  List<MedicationSchedule> get takenMedications {
    return _todaysSchedule.where((s) => s.isTaken).toList();
  }

  // Clear error
  void clearError() {
    _error = null;
    _safeNotify(); // FIXED: Use post-frame callback
  }

  // Add new medication
  Future<bool> addMedication(Map<String, dynamic> data) async {
    _isLoading = true;
    _error = null;
    _safeNotify();

    try {
      await _service.createMedication(data);

      // Reload data to reflect changes
      await loadMedications();
      await loadTodaysSchedule();

      _error = null;
      _safeNotify();
      return true;
    } catch (e) {
      _error = e.toString();
      _safeNotify();
      return false;
    } finally {
      _isLoading = false;
      _safeNotify();
    }
  }

  // Import prescription
  Future<int> importPrescription(String prescriptionId) async {
    _isLoading = true;
    _error = null;
    _safeNotify();

    try {
      final medications = await _service.importPrescription(prescriptionId);

      // Reload to show new medications
      await loadMedications();
      await loadTodaysSchedule();

      _safeNotify();
      return medications.length;
    } catch (e) {
      _error = e.toString();
      _safeNotify();
      return 0;
    } finally {
      _isLoading = false;
      _safeNotify();
    }
  }

  // CRITICAL FIX: Request refresh that can be called during build
  void requestRefresh() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      loadTodaysSchedule();
      loadAdherenceRate();
      loadMedications(); // Also reload medications list
    });
  }
}
