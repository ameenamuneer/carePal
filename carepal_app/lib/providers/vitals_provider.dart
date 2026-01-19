import 'package:flutter/material.dart';
import '../models/vital_reading.dart';
import '../services/vitals_service.dart';

class VitalsProvider with ChangeNotifier {
  final VitalsService _service = VitalsService();

  List<VitalReading> _readings = [];
  List<VitalType> _vitalTypes = [];
  VitalReading? _latestReading;
  bool _isLoading = false;
  String? _error;

  List<VitalReading> get readings => _readings;
  List<VitalType> get vitalTypes => _vitalTypes;
  VitalReading? get latestReading => _latestReading;
  bool get isLoading => _isLoading;
  String? get error => _error;

  // Load vitals readings
  Future<void> loadReadings({String? vitalType, int days = 7}) async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      _readings = await _service.getReadings(vitalType: vitalType, days: days);
    } catch (e) {
      _error = e.toString();
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  // Get latest reading for specific vital
  Future<void> loadLatestReading(String vitalCode) async {
    try {
      _latestReading = await _service.getLatestReading(vitalCode);
      notifyListeners();
    } catch (e) {
      _error = e.toString();
      notifyListeners();
    }
  }

  // Load vital types
  Future<void> loadVitalTypes() async {
    try {
      _vitalTypes = await _service.getVitalTypes();
      notifyListeners();
    } catch (e) {
      _error = e.toString();
      notifyListeners();
    }
  }

  // Create manual entry
  Future<bool> createReading({
    required int vitalTypeId,
    double? value,
    Map<String, dynamic>? values,
    required String unit,
    DateTime? measuredAt,
    String? notes,
  }) async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final reading = await _service.createReading(
        vitalTypeId: vitalTypeId,
        value: value,
        values: values,
        unit: unit,
        measuredAt: measuredAt,
        notes: notes,
      );

      // Add to local list
      _readings.insert(0, reading);
      _latestReading = reading;

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

  // Get readings for specific vital type
  List<VitalReading> getReadingsByType(String vitalCode) {
    return _readings.where((r) => r.vitalCode == vitalCode).toList();
  }

  // Clear error
  void clearError() {
    _error = null;
    notifyListeners();
  }
}
