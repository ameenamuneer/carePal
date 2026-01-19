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
    this.scheduleDetails = const [],
  });

  factory Medication.fromJson(Map<String, dynamic> json) {
    return Medication(
      id: json['id'],
      patientId: json['patient'],
      medicationName: json['medication_name'],
      dosage: json['dosage'],
      instructions: json['instructions'],
      form: json['form'],
      frequency: json['frequency'],
      route: json['route'],
      startDate: DateTime.parse(json['start_date']),
      endDate: json['end_date'] != null
          ? DateTime.parse(json['end_date'])
          : null,
      status: json['status'],
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
    return MedicationSchedule(
      id: json['id'],
      medication: Medication.fromJson(json['medication']),
      scheduledTime: DateTime.parse(json['scheduled_time']),
      status: json['status'],
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
  final DateTime scheduledDate;
  final String status;
  final DateTime? takenAt;
  final String? notes;

  MedicationAdherence({
    required this.id,
    required this.medicationId,
    required this.scheduledDate,
    required this.status,
    this.takenAt,
    this.notes,
  });

  factory MedicationAdherence.fromJson(Map<String, dynamic> json) {
    return MedicationAdherence(
      id: json['id'],
      medicationId: json['medication'],
      scheduledDate: DateTime.parse(json['scheduled_date']),
      status: json['status'],
      takenAt: json['taken_at'] != null
          ? DateTime.parse(json['taken_at'])
          : null,
      notes: json['notes'],
    );
  }
}
