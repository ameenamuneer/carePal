// lib/providers/vitals_provider.dart
// CRITICAL FIX - Prevents setState during build

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

  // CRITICAL FIX: Safe notification helper
  void _safeNotify() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      notifyListeners();
    });
  }

  // Load vitals readings
  // Accepts vitalType (String) for backward compatibility, finds ID
  Future<void> loadReadings({
    int? vitalTypeId,
    String? vitalType,
    int days = 7,
  }) async {
    // CRITICAL FIX: Only set loading if not already loading
    if (_isLoading) return;

    _isLoading = true;
    _error = null;
    _safeNotify(); // FIXED: Use post-frame callback

    try {
      // Resolve vitalTypeId if String code provided
      int? resolvedTypeId = vitalTypeId;
      if (resolvedTypeId == null && vitalType != null) {
        if (_vitalTypes.isEmpty) {
          await _loadVitalTypesSilent();
        }
        final type = _vitalTypes.firstWhere(
          (t) => t.code == vitalType,
          orElse: () =>
              VitalType(id: -1, name: '', code: '', unit: '', category: ''),
        );
        if (type.id != -1) {
          resolvedTypeId = type.id;
        }
      }

      // Calculate start date
      final endDate = DateTime.now();
      final startDate = endDate.subtract(Duration(days: days));

      final response = await _service.getReadings(
        vitalTypeId: resolvedTypeId,
        startDate: startDate.toIso8601String(),
        endDate: endDate.toIso8601String(),
      );

      if (response['results'] != null) {
        _readings = (response['results'] as List)
            .map((i) => VitalReading.fromJson(i))
            .toList();
      } else {
        _readings = [];
      }

      _error = null;
    } catch (e) {
      _error = e.toString();
      debugPrint('Error loading vitals readings: $e');
    } finally {
      _isLoading = false;
      _safeNotify(); // FIXED: Use post-frame callback
    }
  }

  // Get latest reading for specific vital
  // Accepts vitalCode (String) or int ID
  Future<void> loadLatestReading(dynamic vitalIdentifier) async {
    try {
      // First ensure types are loaded to map code to ID if needed
      if (_vitalTypes.isEmpty) {
        await _loadVitalTypesSilent();
      }

      int? vitalTypeId;
      if (vitalIdentifier is int) {
        vitalTypeId = vitalIdentifier;
      } else if (vitalIdentifier is String) {
        final type = _vitalTypes.firstWhere(
          (t) => t.code == vitalIdentifier,
          orElse: () =>
              VitalType(id: -1, name: '', code: '', unit: '', category: ''),
        );
        if (type.id != -1) vitalTypeId = type.id;
      }

      final results = await _service.getLatestReadings();
      final readings = results.map((i) => VitalReading.fromJson(i)).toList();

      if (vitalTypeId != null) {
        try {
          _latestReading = readings.firstWhere(
            (r) => r.vitalTypeId == vitalTypeId,
          );
        } catch (_) {
          _latestReading = null;
        }
      } else {
        if (readings.isNotEmpty) _latestReading = readings.first;
      }

      _safeNotify(); // FIXED: Use post-frame callback
    } catch (e) {
      _error = e.toString();
      _safeNotify(); // FIXED: Use post-frame callback
    }
  }

  // Internal helper to load types without notifying state changes unnecessarily
  Future<void> _loadVitalTypesSilent() async {
    try {
      final response = await _service.getVitalTypes(pageSize: 100);
      if (response['results'] != null) {
        _vitalTypes = (response['results'] as List)
            .map((i) => VitalType.fromJson(i))
            .toList();
      }
    } catch (e) {
      debugPrint('Error loading vital types silent: $e');
    }
  }

  // Load vital types
  Future<void> loadVitalTypes() async {
    try {
      await _loadVitalTypesSilent();
      _safeNotify(); // FIXED: Use post-frame callback
    } catch (e) {
      _error = e.toString();
      _safeNotify(); // FIXED: Use post-frame callback
    }
  }

  // Create manual entry
  Future<bool> createReading({
    required int patientId,
    required int vitalTypeId,
    double? value,
    Map<String, dynamic>? values,
    required String unit,
    DateTime? measuredAt,
    String? notes,
  }) async {
    _isLoading = true;
    _error = null;
    _safeNotify(); // FIXED: Use post-frame callback

    try {
      final response = await _service.createReading(
        patientId: patientId,
        vitalTypeId: vitalTypeId,
        value: value,
        values: values,
        unit: unit,
        measuredAt: measuredAt,
        notes: notes,
      );

      final reading = VitalReading.fromJson(response);

      // Add to local list
      _readings.insert(0, reading);
      _latestReading = reading;

      _error = null;
      _safeNotify(); // FIXED: Use post-frame callback
      return true;
    } catch (e) {
      _error = e.toString();
      debugPrint('Error creating vital reading: $e');
      _safeNotify(); // FIXED: Use post-frame callback
      return false;
    } finally {
      _isLoading = false;
      _safeNotify(); // FIXED: Use post-frame callback
    }
  }

  // Get readings for specific vital type
  // Supports String code lookup
  List<VitalReading> getReadingsByType(dynamic vitalIdentifier) {
    if (vitalIdentifier is int) {
      return _readings.where((r) => r.vitalTypeId == vitalIdentifier).toList();
    } else if (vitalIdentifier is String) {
      // Try to find the type ID
      final type = _vitalTypes.firstWhere(
        (t) => t.code == vitalIdentifier,
        orElse: () =>
            VitalType(id: -1, name: '', code: '', unit: '', category: ''),
      );
      if (type.id != -1) {
        return _readings.where((r) => r.vitalTypeId == type.id).toList();
      }
      return [];
    }
    return [];
  }

  // Clear error
  void clearError() {
    _error = null;
    _safeNotify(); // FIXED: Use post-frame callback
  }

  // CRITICAL FIX: Request refresh that can be called during build
  void requestRefresh({int days = 7}) {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      loadReadings(days: days);
    });
  }
}
