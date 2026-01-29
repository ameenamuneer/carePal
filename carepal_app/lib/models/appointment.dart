class Appointment {
  final int id;
  final int patientId;
  final String doctorName;
  final String clinicName;
  final DateTime appointmentDate;
  final String mode;
  final String status;

  // Eka fields
  final String? ekaAppointmentId;
  final String? ekaDoctorId;
  final String? ekaClinicId;

  // Helpers
  final bool isUpcoming;
  final bool isPast;

  Appointment({
    required this.id,
    required this.patientId,
    required this.doctorName,
    required this.clinicName,
    required this.appointmentDate,
    required this.mode,
    required this.status,
    this.ekaAppointmentId,
    this.ekaDoctorId,
    this.ekaClinicId,
    this.isUpcoming = false,
    this.isPast = false,
  });

  factory Appointment.fromJson(Map<String, dynamic> json) {
    return Appointment(
      id: json['id'] ?? 0,
      patientId: json['patient'] ?? 0,
      doctorName: json['doctor_name'] ?? 'Unknown Doctor',
      clinicName: json['clinic_name'] ?? 'Unknown Clinic',
      appointmentDate: json['appointment_date'] != null
          ? DateTime.parse(json['appointment_date'])
          : DateTime.now(),
      mode: json['mode'] ?? 'INCLINIC',
      status: json['status'] ?? 'BOOKED',
      ekaAppointmentId: json['eka_appointment_id'],
      ekaDoctorId: json['eka_doctor_id'],
      ekaClinicId: json['eka_clinic_id'],
      isUpcoming: json['is_upcoming'] ?? false,
      isPast: json['is_past'] ?? false,
    );
  }
}
