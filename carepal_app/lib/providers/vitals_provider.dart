// lib/providers/vitals_provider.dart
// CRITICAL FIX - Prevents setState during build

import 'package:flutter/material.dart';
import '../models/vital_reading.dart';
import '../services/vitals_service.dart';

class VitalsProvider with ChangeNotifier {
  final VitalsService _service = VitalsService();

  List<VitalReading> _readings = [];
  Map<String, VitalReading> _dashboardVitals = {}; // Legacy: Latest reading map
  Map<String, Map<String, dynamic>> _dashboardSummaries =
      {}; // New: Full summary with history

  List<VitalType> _vitalTypes = [];
  VitalReading? _latestReading;
  bool _isLoading = false;
  String? _error;

  List<VitalReading> get readings => _readings;
  List<VitalReading> get dashboardVitals => _dashboardVitals.values.toList();
  Map<String, Map<String, dynamic>> get dashboardSummaries =>
      _dashboardSummaries; // Expose full summaries
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

  // Helper to resolve vital type ID from code or fuzzy name
  int? _resolveVitalTypeId(dynamic identifier) {
    if (identifier is int) return identifier;
    if (identifier is! String) return null;
    if (_vitalTypes.isEmpty) return null;

    // 1. Exact match on code
    try {
      final type = _vitalTypes.firstWhere((t) => t.code == identifier);
      return type.id;
    } catch (_) {}

    // 2. Fuzzy match
    final search = identifier.toUpperCase();
    for (final type in _vitalTypes) {
      final name = type.name.toUpperCase();
      final code = type.code.toUpperCase();

      if (search == 'HR' &&
          (name.contains('HEART RATE') || code == 'HEART_RATE'))
        return type.id;
      if (search == 'BP' &&
          (name.contains('BLOOD PRESSURE') || code.contains('BP')))
        return type.id;
      if (search == 'TEMP' &&
          (name.contains('TEMPERATURE') || code.contains('TEMP')))
        return type.id;
      if (search == 'SPO2' &&
          (name.contains('OXYGEN') || code.contains('SPO2')))
        return type.id;
    }

    return null;
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
      // Ensure types are loaded
      if (_vitalTypes.isEmpty) {
        await _loadVitalTypesSilent();
      }

      // Resolve vitalTypeId
      int? resolvedTypeId = vitalTypeId;
      if (resolvedTypeId == null && vitalType != null) {
        resolvedTypeId = _resolveVitalTypeId(vitalType);
      }

      // Calculate start date
      final endDate = DateTime.now();
      final startDate = endDate.subtract(Duration(days: days));

      final response = await _service.getReadings(
        vitalTypeId: resolvedTypeId,
        startDate: startDate.toIso8601String(),
        endDate: endDate.toIso8601String(),
        pageSize: 100, // Increase page size to get more history
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

  // NEW: Load dashboard vitals (latest values + history)
  Future<void> loadDashboardVitals() async {
    // Only set loading if not already loading
    if (_isLoading) return;

    _isLoading = true;
    _error = null;
    _safeNotify();

    try {
      if (_vitalTypes.isEmpty) {
        await _loadVitalTypesSilent();
      }

      // Fetch full summary from backend
      final summaryList = await _service.getVitalsSummary();

      // Clear and rebuild maps
      _dashboardVitals.clear();
      _dashboardSummaries.clear();

      for (final item in summaryList) {
        final vitalCode = item['vital_code'] as String? ?? 'UNKNOWN';

        // 1. Polulate Legacy Map (Latest Reading only)
        if (item['latest_reading'] != null) {
          final reading = VitalReading.fromJson(item['latest_reading']);
          _dashboardVitals[vitalCode] = reading;
        }

        // 2. Populate New Map (Full Summary)
        _dashboardSummaries[vitalCode] = item as Map<String, dynamic>;
      }
    } catch (e) {
      _error = e.toString();
      debugPrint('Error loading dashboard vitals: $e');
    } finally {
      _isLoading = false;
      _safeNotify();
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

      int? vitalTypeId = _resolveVitalTypeId(vitalIdentifier);

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

        debugPrint('=== [DEBUG] Loaded ${_vitalTypes.length} Vital Types ===');
        for (var t in _vitalTypes) {
          debugPrint('Type: id=${t.id} code="${t.code}" name="${t.name}"');
        }
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

      // Update dashboard state map
      String code = reading.vitalCode;
      if (code == 'UNKNOWN' && _vitalTypes.isNotEmpty) {
        final type = _vitalTypes.firstWhere(
          (t) => t.id == vitalTypeId,
          orElse: () => VitalType(
            id: -1,
            code: 'UNKNOWN',
            name: '',
            unit: '',
            category: '',
          ),
        );
        if (type.id != -1) code = type.code;
      }
      if (code != 'UNKNOWN') {
        _dashboardVitals[code] = reading;
      }

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
    int? typeId = _resolveVitalTypeId(vitalIdentifier);

    if (typeId != null) {
      return _readings.where((r) => r.vitalTypeId == typeId).toList();
    }

    // Fallback: if resolution failed but we have readings (unlikely if loadReadings used same logic)
    // Return all readings if they seem to match strictly
    if (vitalIdentifier is String) {
      return _readings.where((r) => r.vitalCode == vitalIdentifier).toList();
    }

    return [];
  }

  // Clear error
  void clearError() {
    _error = null;
    _safeNotify();
  }

  // CRITICAL FIX: Request refresh that can be called during build
  void requestRefresh({int days = 7}) {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      loadReadings(days: days);
    });
  }
}
