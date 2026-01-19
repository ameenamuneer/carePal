class MedicationAdherence {
  final int id;
  final int medicationId;
  final String status;
  final DateTime takenAt;
  final String? notes;

  MedicationAdherence({
    required this.id,
    required this.medicationId,
    required this.status,
    required this.takenAt,
    this.notes,
  });

  factory MedicationAdherence.fromJson(Map<String, dynamic> json) {
    return MedicationAdherence(
      id: json['id'],
      medicationId: json['medication'],
      status: json['status'],
      takenAt: DateTime.parse(json['taken_at']),
      notes: json['notes'],
    );
  }
}
