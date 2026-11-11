import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../services/api_service.dart';
import '../services/auth_service.dart';

class AuthProvider with ChangeNotifier {
  final AuthService _authService = AuthService();
  final ApiService _api = ApiService();

  // Cached user payload (same shape as the login response's 'user'), so a
  // restored session shows the dashboard immediately, even offline.
  static const _userCacheKey = 'auth_user';

  bool _isAuthenticated = false;
  bool _isInitializing = true;
  bool _isLoading = false;
  Map<String, dynamic>? _user;
  String? _errorMessage;

  AuthProvider() {
    _api.onSessionExpired = _handleSessionExpired;
  }

  bool get isAuthenticated => _isAuthenticated;

  /// True until restoreSession() has decided whether a saved login exists.
  bool get isInitializing => _isInitializing;
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
      await _cacheUser(_user);
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
      await _cacheUser(_user);
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
    await _cacheUser(null);
    notifyListeners();
  }

  /// Restore a saved login on app start. If the stored session can still be
  /// renewed, go straight to the app (using the cached user), make sure the
  /// access token is fresh, and reload the user profile in the background.
  Future<void> restoreSession() async {
    try {
      if (await _api.hasSession()) {
        _user = await _loadCachedUser();
        _isAuthenticated = true;
        // Renew an expired access token now so the first requests and the
        // live socket start with a valid one. If the server rejects the
        // session, onSessionExpired flips us back to logged out.
        await _api.getValidAccessToken();
        if (_isAuthenticated) {
          if (_user == null) {
            // No cached user yet (logged in before this version): wait for it,
            // screens read the patient id from it.
            await _refreshUser().timeout(const Duration(seconds: 10), onTimeout: () {});
          } else {
            unawaited(_refreshUser());
          }
        }
      }
    } catch (e) {
      debugPrint('Session restore failed: $e');
    } finally {
      _isInitializing = false;
      notifyListeners();
    }
  }

  Future<void> _refreshUser() async {
    try {
      final profile = await _authService.getProfile();
      _user = profile;
      await _cacheUser(profile);
      notifyListeners();
    } catch (_) {
      // Offline or server error: keep the cached user.
    }
  }

  void _handleSessionExpired() {
    if (!_isAuthenticated && _user == null) return;
    _isAuthenticated = false;
    _user = null;
    unawaited(_cacheUser(null));
    notifyListeners();
  }

  Future<Map<String, dynamic>?> _loadCachedUser() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_userCacheKey);
    if (raw == null) return null;
    try {
      return jsonDecode(raw) as Map<String, dynamic>;
    } catch (_) {
      return null;
    }
  }

  Future<void> _cacheUser(Map<String, dynamic>? user) async {
    final prefs = await SharedPreferences.getInstance();
    if (user == null) {
      await prefs.remove(_userCacheKey);
    } else {
      await prefs.setString(_userCacheKey, jsonEncode(user));
    }
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
