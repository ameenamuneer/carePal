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
  final String? notes;

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
    this.notes,
  });

  factory VitalReading.fromJson(Map<String, dynamic> json) {
    return VitalReading(
      id: json['id'],
      patientId: json['patient'],
      vitalTypeId: json['vital_type'],
      vitalCode: json['vital_code'] ?? '',
      vitalName: json['vital_name'] ?? '',
      value: json['value']?.toDouble(),
      values: json['values'],
      unit: json['unit'],
      measuredAt: DateTime.parse(json['measured_at']),
      source: json['source'],
      dataQuality: json['data_quality'] ?? 'GOOD',
      isAnomaly: json['is_anomaly'] ?? false,
      notes: json['notes'],
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
