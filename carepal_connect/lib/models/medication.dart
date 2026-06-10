/// Parses a time-only string like "08:00:00" or a full ISO datetime like
/// "2026-06-10T08:00:00" into a DateTime anchored to today's date.
DateTime _parseScheduledTime(dynamic raw) {
  if (raw == null) return DateTime.now();
  final s = raw.toString();
  if (s.contains('T')) {
    // Full datetime — use as-is
    return DateTime.parse(s);
  }
  // Time-only string: "HH:MM" or "HH:MM:SS"
  final parts = s.split(':');
  if (parts.length >= 2) {
    final now = DateTime.now();
    final h = int.tryParse(parts[0]) ?? 0;
    final m = int.tryParse(parts[1]) ?? 0;
    return DateTime(now.year, now.month, now.day, h, m);
  }
  return DateTime.now();
}

class Medication {
  final int id;
  final int patientId;
  final String medicationName;
  final String dosage;
  final String instructions;
  final String form;
  final String frequency;
  final String route;
  final DateTime startDate;
  final DateTime? endDate;
  final String status;
  final String source;
  final String? ekaPrescriptionId;
  final String? ekaDrugId;
  final List<String> scheduleDetails;

  Medication({
    required this.id,
    required this.patientId,
    required this.medicationName,
    required this.dosage,
    required this.instructions,
    required this.form,
    required this.frequency,
    required this.route,
    required this.startDate,
    this.endDate,
    required this.status,
    this.source = 'MANUAL',
    this.ekaPrescriptionId,
    this.ekaDrugId,
    this.scheduleDetails = const [],
  });

  factory Medication.fromJson(Map<String, dynamic> json) {
    return Medication(
      id: json['id'] ?? 0,
      patientId: json['patient'] ?? 0,
      medicationName: json['medication_name'] ?? 'Unknown Medication',
      dosage: json['dosage'] ?? '',
      instructions: json['instructions'] ?? '',
      form: json['form'] ?? '',
      frequency: json['frequency'] ?? '',
      route: json['route'] ?? '',
      startDate: json['start_date'] != null
          ? DateTime.parse(json['start_date'])
          : DateTime.now(),
      endDate: json['end_date'] != null
          ? DateTime.parse(json['end_date'])
          : null,
      status: json['status'] ?? 'UNKNOWN',
      source: json['source'] ?? 'MANUAL',
      ekaPrescriptionId: json['eka_prescription_id'],
      ekaDrugId: json['eka_drug_id'],
      scheduleDetails: json['schedule_details'] != null
          ? List<String>.from(json['schedule_details'])
          : [],
    );
  }

  bool get isActive => status == 'ACTIVE';
}

class MedicationSchedule {
  final int id;
  final Medication medication;
  final DateTime scheduledTime;
  final String status;
  final DateTime? takenAt;
  final String? notes;

  MedicationSchedule({
    required this.id,
    required this.medication,
    required this.scheduledTime,
    required this.status,
    this.takenAt,
    this.notes,
  });

  factory MedicationSchedule.fromJson(Map<String, dynamic> json) {
    // Handle "Today's Schedule" flat structure from backend
    if (json['medication'] == null && json['medication_name'] != null) {
      return MedicationSchedule(
        id: json['adherence_id'] ?? json['id'] ?? 0,
        medication: Medication(
          id: json['medication_id'] ?? 0,
          patientId: 0,
          medicationName: json['medication_name'] ?? '',
          dosage: json['dosage'] ?? '',
          instructions: json['instructions'] ?? '',
          form: json['form'] ?? '',
          frequency: '',
          route: '',
          startDate: DateTime.now(),
          status: 'ACTIVE',
        ),
        scheduledTime: _parseScheduledTime(json['scheduled_time']),
        status: json['status'] ?? 'SCHEDULED',
        takenAt: json['actual_datetime'] != null
            ? DateTime.parse(json['actual_datetime'])
            : null,
        notes: json['notes'],
      );
    }

    // Handle normal nested structure
    return MedicationSchedule(
      id: json['id'] ?? 0,
      medication: Medication.fromJson(json['medication'] ?? {}),
      scheduledTime: json['scheduled_time'] != null
          ? DateTime.parse(json['scheduled_time'])
          : DateTime.now(),
      status: json['status'] ?? 'SCHEDULED',
      takenAt: json['taken_at'] != null
          ? DateTime.parse(json['taken_at'])
          : null,
      notes: json['notes'],
    );
  }

  bool get isTaken => status == 'TAKEN';
  bool get isMissed => status == 'MISSED';
  bool get isScheduled => status == 'SCHEDULED';
  bool get isSkipped => status == 'SKIPPED';
}

class MedicationAdherence {
  final int id;
  final int medicationId;
  final String medicationName;
  final String dosage;
  final DateTime scheduledDate;
  final String status;
  final DateTime? takenAt;
  final String? notes;
  final String confirmationMethod;
  final int? sourceActivityLogId;

  MedicationAdherence({
    required this.id,
    required this.medicationId,
    required this.medicationName,
    required this.dosage,
    required this.scheduledDate,
    required this.status,
    this.takenAt,
    this.notes,
    this.confirmationMethod = 'MANUAL',
    this.sourceActivityLogId,
  });

  factory MedicationAdherence.fromJson(Map<String, dynamic> json) {
    return MedicationAdherence(
      id: json['id'] ?? 0,
      medicationId: json['medication'] ?? 0,
      medicationName: json['medication_name'] ?? '',
      dosage: json['dosage'] ?? '',
      scheduledDate: json['scheduled_date'] != null
          ? DateTime.parse(json['scheduled_date'])
          : DateTime.now(),
      status: json['status'] ?? 'SCHEDULED',
      takenAt: json['actual_datetime'] != null
          ? DateTime.parse(json['actual_datetime'])
          : null,
      notes: json['notes'],
      confirmationMethod: json['confirmation_method'] ?? 'MANUAL',
      sourceActivityLogId: json['source_activity_log'],
    );
  }
}
