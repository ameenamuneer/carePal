import 'api_service.dart';
import '../models/appointment.dart';

class AppointmentService {
  final ApiService _api = ApiService();

  /// Get available slots from Eka.Care (proxy via backend)
  /// GET /api/v1/appointments/available_slots/
  Future<Map<String, dynamic>> getAvailableSlots({
    required String doctorId,
    required String clinicId,
    required String date,
  }) async {
    try {
      final response = await _api.get(
        '/api/v1/appointments/available_slots/',
        queryParameters: {
          'doctor_id': doctorId,
          'clinic_id': clinicId,
          'date': date,
        },
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to load slots: $e');
    }
  }

  /// Book appointment
  /// POST /api/v1/appointments/book/
  Future<Appointment> bookAppointment({
    required String doctorId,
    required String clinicId,
    required int appointmentTime, // Unix timestamp
    required String doctorName,
    required String clinicName,
    String mode = 'INCLINIC',
  }) async {
    try {
      final response = await _api.post(
        '/api/v1/appointments/book/',
        data: {
          'doctor_id': doctorId,
          'clinic_id': clinicId,
          'appointment_time': appointmentTime,
          'doctor_name': doctorName,
          'clinic_name': clinicName,
          'mode': mode,
        },
      );
      return Appointment.fromJson(response.data['appointment']);
    } catch (e) {
      throw Exception('Failed to book appointment: $e');
    }
  }

  /// Get my appointments
  /// GET /api/v1/appointments/
  Future<List<Appointment>> getMyAppointments() async {
    try {
      final response = await _api.get('/api/v1/appointments/');
      return (response.data as List)
          .map((json) => Appointment.fromJson(json))
          .toList();
    } catch (e) {
      throw Exception('Failed to load appointments: $e');
    }
  }
}
