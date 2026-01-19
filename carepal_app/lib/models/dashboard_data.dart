// Helper functions for robust numeric parsing
double _parseDouble(dynamic value) {
  if (value == null) return 0.0;
  if (value is double) return value;
  if (value is int) return value.toDouble();
  if (value is String) return double.tryParse(value) ?? 0.0;
  return 0.0;
}

int _parseInt(dynamic value) {
  if (value == null) return 0;
  if (value is int) return value;
  if (value is double) return value.toInt();
  if (value is String) return int.tryParse(value) ?? 0;
  return 0;
}

class DashboardData {
  final int patientId;
  final String patientName;
  final HealthScore healthScore;
  final Map<String, VitalSummary> vitalsSummary;
  final MedicationAdherenceSummary medicationAdherence;
  final AlertsSummary alerts;
  final Map<String, RiskAssessment> riskAssessment;
  final List<Insight> insights;
  final List<Recommendation> recommendations;
  final double dataCompleteness;
  final DateTime lastUpdated;

  DashboardData({
    required this.patientId,
    required this.patientName,
    required this.healthScore,
    required this.vitalsSummary,
    required this.medicationAdherence,
    required this.alerts,
    required this.riskAssessment,
    required this.insights,
    required this.recommendations,
    required this.dataCompleteness,
    required this.lastUpdated,
  });

  factory DashboardData.fromJson(Map<String, dynamic> json) {
    return DashboardData(
      patientId: _parseInt(json['patient_id']),
      patientName: json['patient_name'],
      healthScore: HealthScore.fromJson(json['health_score']),
      vitalsSummary: (json['vitals_summary'] as Map<String, dynamic>).map(
        (key, value) => MapEntry(key, VitalSummary.fromJson(value)),
      ),
      medicationAdherence: MedicationAdherenceSummary.fromJson(
        json['medication_adherence'],
      ),
      alerts: AlertsSummary.fromJson(json['alerts']),
      riskAssessment: (json['risk_assessment'] as Map<String, dynamic>).map(
        (key, value) => MapEntry(key, RiskAssessment.fromJson(value)),
      ),
      insights:
          (json['insights'] as List?)
              ?.map((i) => Insight.fromJson(i))
              .toList() ??
          [],
      recommendations:
          (json['recommendations'] as List?)
              ?.map((r) => Recommendation.fromJson(r))
              .toList() ??
          [],
      dataCompleteness: _parseDouble(json['data_completeness']),
      lastUpdated: DateTime.parse(json['last_updated']),
    );
  }
}

class HealthScore {
  final int score;
  final String category;
  final String trend;

  HealthScore({
    required this.score,
    required this.category,
    required this.trend,
  });

  factory HealthScore.fromJson(Map<String, dynamic> json) {
    return HealthScore(
      score: _parseInt(json['score']),
      category: json['category'],
      trend: json['trend'],
    );
  }
}

class VitalSummary {
  final int readingsCount;
  final double? average;
  final double? minimum;
  final double? maximum;
  final int anomalyCount;
  final String trend;
  final Map<String, dynamic>? latestReading;

  VitalSummary({
    required this.readingsCount,
    this.average,
    this.minimum,
    this.maximum,
    required this.anomalyCount,
    required this.trend,
    this.latestReading,
  });

  factory VitalSummary.fromJson(Map<String, dynamic> json) {
    return VitalSummary(
      readingsCount: _parseInt(json['readings_count']),
      average: json['average'] != null ? _parseDouble(json['average']) : null,
      minimum: json['minimum'] != null ? _parseDouble(json['minimum']) : null,
      maximum: json['maximum'] != null ? _parseDouble(json['maximum']) : null,
      anomalyCount: _parseInt(json['anomaly_count'] ?? 0),
      trend: json['trend'] ?? 'stable',
      latestReading: json['latest_reading'],
    );
  }
}

class MedicationAdherenceSummary {
  final double rate;
  final int totalScheduled;
  final int totalTaken;
  final String trend;

  MedicationAdherenceSummary({
    required this.rate,
    required this.totalScheduled,
    required this.totalTaken,
    required this.trend,
  });

  factory MedicationAdherenceSummary.fromJson(Map<String, dynamic> json) {
    return MedicationAdherenceSummary(
      rate: _parseDouble(json['rate']),
      totalScheduled: _parseInt(json['total_scheduled']),
      totalTaken: _parseInt(json['total_taken']),
      trend: json['trend'] ?? 'stable',
    );
  }
}

class AlertsSummary {
  final int total;
  final Map<String, int> bySeverity;
  final double? avgResponseTime;

  AlertsSummary({
    required this.total,
    required this.bySeverity,
    this.avgResponseTime,
  });

  factory AlertsSummary.fromJson(Map<String, dynamic> json) {
    return AlertsSummary(
      total: _parseInt(json['total']),
      bySeverity: Map<String, int>.from(json['by_severity']),
      avgResponseTime: json['avg_response_time'] != null
          ? _parseDouble(json['avg_response_time'])
          : null,
    );
  }
}

class RiskAssessment {
  final double score;
  final String category;
  final List<String> factors;

  RiskAssessment({
    required this.score,
    required this.category,
    required this.factors,
  });

  factory RiskAssessment.fromJson(Map<String, dynamic> json) {
    return RiskAssessment(
      score: _parseDouble(json['score']),
      category: json['category'],
      factors: List<String>.from(json['factors']),
    );
  }
}

class Insight {
  final String type;
  final String severity;
  final String title;
  final String message;
  final DateTime generatedAt;

  Insight({
    required this.type,
    required this.severity,
    required this.title,
    required this.message,
    required this.generatedAt,
  });

  factory Insight.fromJson(dynamic json) {
    // Handle string inputs (simple messages from backend)
    if (json is String) {
      return Insight(
        type: 'general',
        severity: 'info',
        title: 'Health Insight',
        message: json,
        generatedAt: DateTime.now(),
      );
    }

    // Handle map inputs (structured objects)
    if (json is Map<String, dynamic>) {
      return Insight(
        type: json['type'] ?? 'general',
        severity: json['severity'] ?? 'info',
        title: json['title'] ?? 'Health Insight',
        message: json['message'] ?? json.toString(),
        generatedAt: json['generated_at'] != null
            ? DateTime.parse(json['generated_at'])
            : DateTime.now(),
      );
    }

    // Fallback for unknown types
    return Insight(
      type: 'unknown',
      severity: 'info',
      title: 'Insight',
      message: json.toString(),
      generatedAt: DateTime.now(),
    );
  }
}

class Recommendation {
  final String category;
  final String title;
  final String description;
  final int priority;

  Recommendation({
    required this.category,
    required this.title,
    required this.description,
    required this.priority,
  });

  factory Recommendation.fromJson(dynamic json) {
    // Handle string inputs
    if (json is String) {
      return Recommendation(
        category: 'general',
        title: 'Recommendation',
        description: json,
        priority: 1,
      );
    }

    // Handle map inputs
    if (json is Map<String, dynamic>) {
      return Recommendation(
        category: json['category'] ?? 'general',
        title: json['title'] ?? 'Recommendation',
        description: json['description'] ?? json.toString(),
        priority: json['priority'] ?? 1,
      );
    }

    // Fallback
    return Recommendation(
      category: 'general',
      title: 'Recommendation',
      description: json.toString(),
      priority: 1,
    );
  }
}
