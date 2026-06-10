class ClinicalRelationship {
  final int id;
  final int doctor;
  final String doctorName;
  final int patient;
  final String patientName;
  final String role; // PRIMARY, SPECIALIST, NURSE, CONSULTANT
  final bool isActive;
  final bool canViewVitals;
  final bool canViewActivityLog;
  final bool canViewMedications;
  final bool canEditMedications;
  final bool canViewAlerts;
  final bool canViewAppointments;
  final bool canEditAppointments;
  final String notes;
  final DateTime createdAt;

  ClinicalRelationship({
    required this.id,
    required this.doctor,
    required this.doctorName,
    required this.patient,
    required this.patientName,
    required this.role,
    required this.isActive,
    required this.canViewVitals,
    required this.canViewActivityLog,
    required this.canViewMedications,
    required this.canEditMedications,
    required this.canViewAlerts,
    required this.canViewAppointments,
    required this.canEditAppointments,
    required this.notes,
    required this.createdAt,
  });

  factory ClinicalRelationship.fromJson(Map<String, dynamic> json) {
    return ClinicalRelationship(
      id: json['id'],
      doctor: json['doctor'],
      doctorName: json['doctor_name'] ?? '',
      patient: json['patient'],
      patientName: json['patient_name'] ?? '',
      role: json['role'] ?? 'PRIMARY',
      isActive: json['is_active'] ?? true,
      canViewVitals: json['can_view_vitals'] ?? false,
      canViewActivityLog: json['can_view_activity_log'] ?? false,
      canViewMedications: json['can_view_medications'] ?? false,
      canEditMedications: json['can_edit_medications'] ?? false,
      canViewAlerts: json['can_view_alerts'] ?? false,
      canViewAppointments: json['can_view_appointments'] ?? false,
      canEditAppointments: json['can_edit_appointments'] ?? false,
      notes: json['notes'] ?? '',
      createdAt: DateTime.parse(
          json['created_at'] ?? DateTime.now().toIso8601String()),
    );
  }
}

class FamilyMemberLink {
  final int id;
  final int user;
  final int patient;
  final String patientName;
  final String relationship; // SPOUSE, CHILD, PARENT, SIBLING, OTHER
  final bool isActive;
  final bool canViewVitals;
  final bool canViewMedications;
  final bool canViewActivityLog;
  final bool canViewAlerts;
  final bool canAcknowledgeAlerts;

  FamilyMemberLink({
    required this.id,
    required this.user,
    required this.patient,
    required this.patientName,
    required this.relationship,
    required this.isActive,
    required this.canViewVitals,
    required this.canViewMedications,
    required this.canViewActivityLog,
    required this.canViewAlerts,
    required this.canAcknowledgeAlerts,
  });

  factory FamilyMemberLink.fromJson(Map<String, dynamic> json) {
    return FamilyMemberLink(
      id: json['id'],
      user: json['user'],
      patient: json['patient'],
      patientName: json['patient_name'] ?? '',
      relationship: json['relationship'] ?? 'OTHER',
      isActive: json['is_active'] ?? true,
      canViewVitals: json['can_view_vitals'] ?? false,
      canViewMedications: json['can_view_medications'] ?? false,
      canViewActivityLog: json['can_view_activity_log'] ?? false,
      canViewAlerts: json['can_view_alerts'] ?? false,
      canAcknowledgeAlerts: json['can_acknowledge_alerts'] ?? false,
    );
  }
}
