import 'package:flutter/foundation.dart';

class VitalReading {
  final int id;
  final int patientId;
  final int vitalTypeId;
  final String vitalCode;
  final String vitalName;
  final double? value;
  final Map<String, dynamic>? values;
  final String unit;
  final DateTime measuredAt;
  final String source;
  final String dataQuality;
  final bool isAnomaly;
  final String anomalySeverity;
  final String? notes;

  final String? remoteDisplayValue; // Store backend-computed display value

  VitalReading({
    required this.id,
    required this.patientId,
    required this.vitalTypeId,
    required this.vitalCode,
    required this.vitalName,
    this.value,
    this.values,
    required this.unit,
    required this.measuredAt,
    required this.source,
    this.dataQuality = 'GOOD',
    this.isAnomaly = false,
    this.anomalySeverity = 'NORMAL',
    this.notes,
    this.remoteDisplayValue,
  });

  factory VitalReading.fromJson(Map<String, dynamic> json) {
    // DEBUG: Inspect raw JSON for vital type
    if (json['id'] == 26 || json['id'] == 24) {
      // Inspect specific IDs from logs
      debugPrint(
        'VitalReading JSON (ID ${json['id']}): vital_type=${json['vital_type']} (${json['vital_type'].runtimeType}), detail=${json['vital_type_detail']}',
      );
    }

    // Helper to safely parse double from dynamic value
    double? parseDouble(dynamic val) {
      if (val == null) return null;
      if (val is num) return val.toDouble();
      if (val is String) return double.tryParse(val);
      return null;
    }

    // Helper to safely parse int
    int parseInt(dynamic val, [int defaultVal = 0]) {
      if (val == null) return defaultVal;
      if (val is int) return val;
      if (val is String) return int.tryParse(val) ?? defaultVal;
      return defaultVal;
    }

    // Helper to safely extract string
    String parseString(dynamic val, [String defaultVal = '']) {
      return val?.toString() ?? defaultVal;
    }

    // Extract vital details from nested object if available
    String code = parseString(json['vital_code']);
    String name = parseString(json['vital_name']);

    if (json['vital_type_detail'] != null && json['vital_type_detail'] is Map) {
      final detail = json['vital_type_detail'];
      if (code.isEmpty) code = parseString(detail['code']);
      if (name.isEmpty) name = parseString(detail['name']);
    }

    // Robust ID extraction for vital_type
    int vTypeId = 0;
    if (json['vital_type'] is int) {
      vTypeId = json['vital_type'];
    } else if (json['vital_type'] is Map) {
      vTypeId = parseInt(json['vital_type']['id']);
    } else {
      vTypeId = parseInt(json['vital_type']);
    }

    if (json['vital_type_detail'] != null && json['vital_type_detail'] is Map) {
      final detail = json['vital_type_detail'];
      // Fallback ID if missing
      if (vTypeId == 0) vTypeId = parseInt(detail['id']);
    }

    // Robust ID extraction for patient
    int pId = 0;
    if (json['patient'] is int) {
      pId = json['patient'];
    } else if (json['patient'] is Map) {
      pId = parseInt(json['patient']['id']);
    } else {
      pId = parseInt(json['patient']);
    }

    // Handle anomaly severity mapping if is_anomaly boolean is missing
    bool anomaly = false;
    String severity = parseString(json['anomaly_severity'], 'NORMAL');

    if (json['is_anomaly'] != null) {
      anomaly = json['is_anomaly'] == true;
    } else if (severity != 'NORMAL') {
      anomaly = true;
    }

    return VitalReading(
      id: parseInt(json['id']),
      patientId: pId,
      vitalTypeId: vTypeId,
      vitalCode: code,
      vitalName: name,
      value: parseDouble(json['value']),
      values: json['values'],
      unit: parseString(json['unit']),
      measuredAt: json['measured_at'] != null
          ? DateTime.parse(json['measured_at'].toString())
          : DateTime.now(),
      source: parseString(json['source'], 'MANUAL'),
      dataQuality: parseString(json['data_quality'], 'GOOD'),
      isAnomaly: anomaly,
      anomalySeverity: severity,
      notes: parseString(json['notes'], ''),
      remoteDisplayValue: json['display_value'], // Capture prompt from backend
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'patient': patientId,
      'vital_type': vitalTypeId,
      if (value != null) 'value': value,
      if (values != null) 'values': values,
      'unit': unit,
      'measured_at': measuredAt.toIso8601String(),
      'source': source,
      'data_quality': dataQuality,
      'is_anomaly': isAnomaly,
      if (notes != null) 'notes': notes,
    };
  }

  String get displayValue {
    // 1. Prefer remote display value if available (from backend)
    if (remoteDisplayValue != null &&
        remoteDisplayValue!.isNotEmpty &&
        remoteDisplayValue != 'N/A') {
      return remoteDisplayValue!;
    }

    // 2. Fallback to local computation
    if (values != null && values!.containsKey('systolic')) {
      // Blood Pressure
      return '${values!['systolic']}/${values!['diastolic']}';
    }
    return value?.toStringAsFixed(1) ?? '--';
  }
}

class VitalType {
  final int id;
  final String code;
  final String name;
  final String unit;
  final String category;
  final Map<String, dynamic>? normalRange;

  VitalType({
    required this.id,
    required this.code,
    required this.name,
    required this.unit,
    required this.category,
    this.normalRange,
  });

  factory VitalType.fromJson(Map<String, dynamic> json) {
    return VitalType(
      id: json['id'],
      code: json['code'],
      name: json['name'],
      unit: json['unit'],
      category: json['category'],
      normalRange: json['normal_range'],
    );
  }
}
