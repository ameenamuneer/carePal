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

  // Load today's schedule
  Future<void> loadTodaysSchedule() async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      _todaysSchedule = await _service.getTodaysSchedule();
    } catch (e) {
      _error = e.toString();
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  // Load all medications
  Future<void> loadMedications({String? status}) async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      _medications = await _service.getMedications(status: status);
    } catch (e) {
      _error = e.toString();
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  // Log medication as taken
  Future<bool> markAsTaken(int adherenceId, {String? notes}) async {
    _isLoading = true;
    _error = null;
    notifyListeners();

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

      notifyListeners();
      return true;
    } catch (e) {
      _error = e.toString();
      notifyListeners();
      return false;
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  // Skip medication
  Future<bool> skipMedication(int adherenceId, String reason) async {
    _isLoading = true;
    _error = null;
    notifyListeners();

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

      notifyListeners();
      return true;
    } catch (e) {
      _error = e.toString();
      notifyListeners();
      return false;
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  // Load adherence history
  Future<void> loadAdherenceHistory({int? medicationId, int days = 30}) async {
    try {
      _adherenceHistory = await _service.getAdherenceHistory(
        medicationId: medicationId,
        days: days,
      );
      notifyListeners();
    } catch (e) {
      _error = e.toString();
      notifyListeners();
    }
  }

  // Load adherence rate
  Future<void> loadAdherenceRate({int days = 7}) async {
    try {
      _adherenceRate = await _service.getAdherenceRate(days);
      notifyListeners();
    } catch (e) {
      _error = e.toString();
      notifyListeners();
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
    notifyListeners();
  }
}
