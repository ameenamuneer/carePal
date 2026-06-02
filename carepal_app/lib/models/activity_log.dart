class ActivityLog {
  final int id;
  final int patient;
  final String patientName;
  final int? session;
  final String? sessionId;
  final String activityType;
  final String description;
  final Map<String, dynamic> details;
  final DateTime observedAt;
  final DateTime loggedAt;
  final Map<String, dynamic> vitalsSnapshot;
  final String aiConfidence;
  final bool isNotable;
  final String? notableReason;
  final List<String> tags;

  ActivityLog({
    required this.id,
    required this.patient,
    required this.patientName,
    this.session,
    this.sessionId,
    required this.activityType,
    required this.description,
    required this.details,
    required this.observedAt,
    required this.loggedAt,
    required this.vitalsSnapshot,
    required this.aiConfidence,
    required this.isNotable,
    this.notableReason,
    required this.tags,
  });

  factory ActivityLog.fromJson(Map<String, dynamic> json) {
    return ActivityLog(
      id: json['id'],
      patient: json['patient'],
      patientName: json['patient_name'] ?? '',
      session: json['session'],
      sessionId: json['session_id'],
      activityType: json['activity_type'] ?? 'OTHER',
      description: json['description'] ?? '',
      details: Map<String, dynamic>.from(json['details'] ?? {}),
      observedAt: DateTime.parse(json['observed_at']),
      loggedAt: DateTime.parse(json['logged_at']),
      vitalsSnapshot: Map<String, dynamic>.from(json['vitals_snapshot'] ?? {}),
      aiConfidence: json['ai_confidence'] ?? 'MEDIUM',
      isNotable: json['is_notable'] ?? false,
      notableReason: json['notable_reason'],
      tags: List<String>.from(json['tags'] ?? []),
    );
  }
}
