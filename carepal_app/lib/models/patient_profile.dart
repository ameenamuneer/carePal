class PatientProfile {
  final int id;
  final String firstName;
  final String lastName;

  // Eka.Care fields
  final String? ekaPatientId;
  final bool ekaPatientCreated;

  // ABHA fields
  final String? abhaNumber;
  final String? abhaAddress;
  final bool isAbhaVerified;

  PatientProfile({
    required this.id,
    required this.firstName,
    required this.lastName,
    this.ekaPatientId,
    this.ekaPatientCreated = false,
    this.abhaNumber,
    this.abhaAddress,
    this.isAbhaVerified = false,
  });

  factory PatientProfile.fromJson(Map<String, dynamic> json) {
    // Handle user object nested or flat
    final user = json['user'] ?? {};
    final firstName = json['first_name'] ?? user['first_name'] ?? '';
    final lastName = json['last_name'] ?? user['last_name'] ?? '';

    return PatientProfile(
      id: json['id'],
      firstName: firstName,
      lastName: lastName,
      ekaPatientId: json['eka_patient_id'],
      ekaPatientCreated: json['eka_patient_created'] ?? false,
      abhaNumber: json['abha_number'],
      abhaAddress: json['abha_address'],
      isAbhaVerified: json['is_abha_verified'] ?? false,
    );
  }

  String get partnerPatientId => 'carepal_$id';

  bool get hasEkaPatient => ekaPatientId != null && ekaPatientId!.isNotEmpty;
  bool get hasAbha => abhaNumber != null && abhaNumber!.isNotEmpty;

  String get displayName => '$firstName $lastName';
}
