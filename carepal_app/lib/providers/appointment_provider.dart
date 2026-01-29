import 'package:flutter/foundation.dart';
import '../models/appointment.dart';
import '../services/appointment_service.dart';

class AppointmentProvider with ChangeNotifier {
  final AppointmentService _service = AppointmentService();

  List<Appointment> _appointments = [];
  bool _isLoading = false;
  String? _error;

  List<Appointment> get appointments => _appointments;
  bool get isLoading => _isLoading;
  String? get error => _error;

  List<Appointment> get upcomingAppointments =>
      _appointments.where((a) => a.isUpcoming).toList();

  List<Appointment> get pastAppointments =>
      _appointments.where((a) => a.isPast).toList();

  // Load appointments
  Future<void> loadAppointments() async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      _appointments = await _service.getMyAppointments();
    } catch (e) {
      _error = e.toString();
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  // Get available slots
  Future<Map<String, dynamic>?> getAvailableSlots({
    required String doctorId,
    required String clinicId,
    required String date,
  }) async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      return await _service.getAvailableSlots(
        doctorId: doctorId,
        clinicId: clinicId,
        date: date,
      );
    } catch (e) {
      _error = e.toString();
      notifyListeners();
      return null;
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  // Book appointment
  Future<bool> bookAppointment({
    required String doctorId,
    required String clinicId,
    required int appointmentTime,
    required String doctorName,
    required String clinicName,
    String mode = 'INCLINIC',
  }) async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final appointment = await _service.bookAppointment(
        doctorId: doctorId,
        clinicId: clinicId,
        appointmentTime: appointmentTime,
        doctorName: doctorName,
        clinicName: clinicName,
        mode: mode,
      );

      _appointments.add(appointment);
      _appointments.sort(
        (a, b) => b.appointmentDate.compareTo(a.appointmentDate),
      );

      return true;
    } catch (e) {
      _error = e.toString();
      notifyListeners();
      return false;
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }
}
