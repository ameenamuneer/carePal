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
      patientId: json['patient_id'],
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
      insights: (json['insights'] as List)
          .map((i) => Insight.fromJson(i))
          .toList(),
      recommendations: (json['recommendations'] as List)
          .map((r) => Recommendation.fromJson(r))
          .toList(),
      dataCompleteness: (json['data_completeness'] as num).toDouble(),
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
      score: json['score'],
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
      readingsCount: json['readings_count'],
      average: json['average']?.toDouble(),
      minimum: json['minimum']?.toDouble(),
      maximum: json['maximum']?.toDouble(),
      anomalyCount: json['anomaly_count'] ?? 0,
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
      rate: (json['rate'] as num).toDouble(),
      totalScheduled: json['total_scheduled'],
      totalTaken: json['total_taken'],
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
      total: json['total'],
      bySeverity: Map<String, int>.from(json['by_severity']),
      avgResponseTime: json['avg_response_time']?.toDouble(),
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
      score: (json['score'] as num).toDouble(),
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

  factory Insight.fromJson(Map<String, dynamic> json) {
    return Insight(
      type: json['type'],
      severity: json['severity'],
      title: json['title'],
      message: json['message'],
      generatedAt: DateTime.parse(json['generated_at']),
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

  factory Recommendation.fromJson(Map<String, dynamic> json) {
    return Recommendation(
      category: json['category'],
      title: json['title'],
      description: json['description'],
      priority: json['priority'],
    );
  }
}
