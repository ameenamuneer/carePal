import 'package:flutter/material.dart';
import '../services/auth_service.dart';

class AuthProvider with ChangeNotifier {
  final AuthService _authService = AuthService();

  bool _isAuthenticated = false;
  bool _isLoading = false;
  Map<String, dynamic>? _user;
  String? _errorMessage;

  bool get isAuthenticated => _isAuthenticated;
  bool get isLoading => _isLoading;
  Map<String, dynamic>? get user => _user;
  String? get errorMessage => _errorMessage;

  Future<bool> login(String username, String password) async {
    _setLoading(true);
    try {
      final data = await _authService.login(
        username: username,
        password: password,
      );

      // Save tokens
      final tokens = data['tokens'];
      await _authService.saveTokens(tokens['access'], tokens['refresh']);

      // Update state
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
    _setLoading(true);
    try {
      final data = await _authService.register(
        username: userData['username'],
        email: userData['email'],
        phoneNumber: userData['phoneNumber'] ?? userData['phone_number'],
        password: userData['password'],
        passwordConfirm:
            userData['passwordConfirm'] ?? userData['password_confirm'],
        userType: userData['userType'] ?? userData['user_type'] ?? 'PATIENT',
        firstName: userData['firstName'] ?? userData['first_name'],
        lastName: userData['lastName'] ?? userData['last_name'],
        dateOfBirth: userData['dateOfBirth'] ?? userData['date_of_birth'],
      );

      // Auto login after register
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
    try {
      // Ideally getting refresh token from storage, but simplifying for now
      // The ApiService.clearTokens() is called inside AuthService.logout anyway
      // if we modify it to read from storage.
      // For now, let's just clear local state as the backend logout requires refresh token
      // which we haven't exposed a reader for in this simple provider yet.
      await _authService.logout();
    } catch (_) {
      // Ignore logout errors
    }
    _isAuthenticated = false;
    _user = null;
    notifyListeners();
  }

  // Check initial auth state (e.g. on app start)
  Future<void> checkAuthStatus() async {
    // Basic check - try fetching profile
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
