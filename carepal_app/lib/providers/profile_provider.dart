// lib/providers/profile_provider.dart
import 'package:flutter/foundation.dart';
import '../services/auth_service.dart';
import '../services/patient_service.dart';

class ProfileProvider with ChangeNotifier {
  final AuthService _authService = AuthService();
  final PatientService _patientService = PatientService();

  // State
  Map<String, dynamic>? _userProfile;
  Map<String, dynamic>? _patientProfile;
  List<dynamic> _emergencyContacts = [];
  bool _isLoading = false;
  String? _error;

  // Getters
  Map<String, dynamic>? get userProfile => _userProfile;
  Map<String, dynamic>? get patientProfile => _patientProfile;
  List<dynamic> get emergencyContacts => _emergencyContacts;
  bool get isLoading => _isLoading;
  String? get error => _error;

  // Computed getters
  String get fullName {
    if (_userProfile == null) return 'User';
    final firstName = _userProfile!['first_name'] ?? '';
    final lastName = _userProfile!['last_name'] ?? '';
    return '$firstName $lastName'.trim();
  }

  String get email => _userProfile?['email'] ?? 'user@example.com';
  String get phoneNumber => _userProfile?['phone_number'] ?? '';
  String get userType => _userProfile?['user_type'] ?? 'PATIENT';

  // Patient profile getters
  int? get patientId => _patientProfile?['id'];
  String get gender => _patientProfile?['gender'] ?? 'Not specified';
  String get bloodGroup => _patientProfile?['blood_group'] ?? 'Unknown';
  double? get heightCm => _patientProfile?['height_cm']?.toDouble();
  double? get weightKg => _patientProfile?['weight_kg']?.toDouble();
  String get city => _patientProfile?['city'] ?? '';
  String get state => _patientProfile?['state'] ?? '';
  String get preferredLanguage =>
      _patientProfile?['preferred_language'] ?? 'English';
  List<dynamic> get healthConditions =>
      _patientProfile?['health_conditions'] ?? [];
  List<dynamic> get allergies => _patientProfile?['allergies'] ?? [];
  String get medicalNotes => _patientProfile?['medical_notes'] ?? '';

  // Load complete profile
  Future<void> loadProfile() async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      // Load user profile (includes basic patient info)
      _userProfile = await _authService.getProfile();

      // If user is a patient, load full patient profile
      if (_userProfile!['user_type'] == 'PATIENT') {
        try {
          _patientProfile = await _patientService.getMyProfile();

          // Load emergency contacts
          if (_patientProfile!['id'] != null) {
            await loadEmergencyContacts(_patientProfile!['id']);
          }
        } catch (e) {
          print('Error loading patient profile: $e');
          // Don't fail entire profile load if patient profile fails
        }
      }

      _error = null;
    } catch (e) {
      _error = 'Failed to load profile: $e';
      print(_error);
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  // Load emergency contacts
  Future<void> loadEmergencyContacts(int patientId) async {
    try {
      final response = await _patientService.getEmergencyContacts(
        patientId: patientId,
        pageSize: 50,
      );
      _emergencyContacts = response['results'] ?? [];
      notifyListeners();
    } catch (e) {
      print('Error loading emergency contacts: $e');
    }
  }

  // Update user profile
  Future<bool> updateUserProfile(Map<String, dynamic> data) async {
    try {
      _userProfile = await _authService.patchProfile(data);
      notifyListeners();
      return true;
    } catch (e) {
      _error = 'Failed to update profile: $e';
      notifyListeners();
      return false;
    }
  }

  // Update patient profile
  Future<bool> updatePatientProfile(Map<String, dynamic> data) async {
    if (patientId == null) return false;

    try {
      _patientProfile = await _patientService.patchPatientProfile(
        patientId!,
        data,
      );
      notifyListeners();
      return true;
    } catch (e) {
      _error = 'Failed to update patient profile: $e';
      notifyListeners();
      return false;
    }
  }

  // Add emergency contact
  Future<bool> addEmergencyContact(Map<String, dynamic> data) async {
    if (patientId == null) return false;

    try {
      await _patientService.createEmergencyContact(
        patientId: patientId!,
        name: data['name'],
        relationship: data['relationship'],
        phoneNumber: data['phone_number'],
        alternatePhone: data['alternate_phone'],
        email: data['email'],
        isPrimary: data['is_primary'] ?? false,
        priorityOrder: data['priority_order'] ?? 1,
        notes: data['notes'],
      );

      // Reload emergency contacts
      await loadEmergencyContacts(patientId!);
      return true;
    } catch (e) {
      _error = 'Failed to add emergency contact: $e';
      notifyListeners();
      return false;
    }
  }

  // Update emergency contact
  Future<bool> updateEmergencyContact(
    int contactId,
    Map<String, dynamic> data,
  ) async {
    try {
      await _patientService.patchEmergencyContact(contactId, data);

      // Reload emergency contacts
      if (patientId != null) {
        await loadEmergencyContacts(patientId!);
      }
      return true;
    } catch (e) {
      _error = 'Failed to update emergency contact: $e';
      notifyListeners();
      return false;
    }
  }

  // Delete emergency contact
  Future<bool> deleteEmergencyContact(int contactId) async {
    try {
      await _patientService.deleteEmergencyContact(contactId);

      // Reload emergency contacts
      if (patientId != null) {
        await loadEmergencyContacts(patientId!);
      }
      return true;
    } catch (e) {
      _error = 'Failed to delete emergency contact: $e';
      notifyListeners();
      return false;
    }
  }

  // Refresh profile
  Future<void> refresh() async {
    await loadProfile();
  }

  // Clear profile data
  void clear() {
    _userProfile = null;
    _patientProfile = null;
    _emergencyContacts = [];
    _error = null;
    notifyListeners();
  }
}
