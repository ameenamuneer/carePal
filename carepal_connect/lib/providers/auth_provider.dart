import 'package:flutter/material.dart';
import '../services/auth_service.dart';
import 'patient_provider.dart';
import 'activity_log_provider.dart';
import 'medication_provider.dart';

class AuthProvider with ChangeNotifier {
  final AuthService _authService = AuthService();

  // Sibling providers to clear on session change.
  // Set once from main.dart after the provider tree is built.
  PatientProvider? _patientProvider;
  ActivityLogProvider? _activityLogProvider;
  MedicationProvider? _medicationProvider;

  void bindDependentProviders(
    PatientProvider patientProvider,
    ActivityLogProvider activityLogProvider,
    MedicationProvider medicationProvider,
  ) {
    _patientProvider = patientProvider;
    _activityLogProvider = activityLogProvider;
    _medicationProvider = medicationProvider;
  }

  void _clearDependentProviders() {
    _patientProvider?.clear();
    _activityLogProvider?.clear();
    _medicationProvider?.clear();
  }

  bool _isAuthenticated = false;
  bool _isLoading = false;
  Map<String, dynamic>? _user;
  String? _errorMessage;

  bool get isAuthenticated => _isAuthenticated;
  bool get isLoading => _isLoading;
  Map<String, dynamic>? get user => _user;
  String? get errorMessage => _errorMessage;

  String get userType => _user?['user_type'] ?? 'FAMILY';
  int get userId => _user?['id'] ?? 0;
  String get userFullName =>
      '${_user?['first_name'] ?? ''} ${_user?['last_name'] ?? ''}'.trim();

  bool get isDoctor => userType == 'DOCTOR';
  bool get isFamily => userType == 'FAMILY';

  Future<bool> login(String username, String password) async {
    _clearDependentProviders();
    _setLoading(true);
    try {
      final data = await _authService.login(
        username: username,
        password: password,
      );

      final tokens = data['tokens'];
      await _authService.saveTokens(tokens['access'], tokens['refresh']);

      _user = data['user'];
      _isAuthenticated = true;
      _errorMessage = null;
      notifyListeners();
      return true;
    } catch (e) {
      _errorMessage = e.toString();
      _isAuthenticated = false;
      notifyListeners();
      return false;
    } finally {
      _setLoading(false);
    }
  }

  Future<bool> register(Map<String, dynamic> userData) async {
    _clearDependentProviders();
    _setLoading(true);
    try {
      final data = await _authService.register(
        username: userData['username'],
        email: userData['email'],
        phoneNumber: userData['phoneNumber'] ?? userData['phone_number'] ?? '',
        password: userData['password'],
        passwordConfirm:
            userData['passwordConfirm'] ?? userData['password_confirm'],
        userType: userData['userType'] ?? userData['user_type'] ?? 'FAMILY',
        firstName: userData['firstName'] ?? userData['first_name'],
        lastName: userData['lastName'] ?? userData['last_name'],
      );

      final tokens = data['tokens'];
      await _authService.saveTokens(tokens['access'], tokens['refresh']);

      _user = data['user'];
      _isAuthenticated = true;
      _errorMessage = null;
      notifyListeners();
      return true;
    } catch (e) {
      _errorMessage = e.toString();
      notifyListeners();
      return false;
    } finally {
      _setLoading(false);
    }
  }

  Future<void> logout() async {
    _clearDependentProviders();
    try {
      await _authService.logout();
    } catch (_) {}
    _isAuthenticated = false;
    _user = null;
    notifyListeners();
  }

  Future<void> checkAuthStatus() async {
    try {
      final profile = await _authService.getProfile();
      _user = profile;
      _isAuthenticated = true;
    } catch (_) {
      _isAuthenticated = false;
      _user = null;
    }
    notifyListeners();
  }

  void _setLoading(bool value) {
    _isLoading = value;
    notifyListeners();
  }
}
