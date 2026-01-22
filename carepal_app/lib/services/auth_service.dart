import 'package:dio/dio.dart';
import 'api_service.dart';

/// Complete Authentication Service
/// Maps to backend/users/views.py
class AuthService {
  final ApiService _api = ApiService();

  // ==================== REGISTRATION ====================

  /// Register a new user
  /// POST /api/v1/auth/register/
  Future<Map<String, dynamic>> register({
    required String username,
    required String email,
    required String phoneNumber,
    required String password,
    required String passwordConfirm,
    required String userType, // PATIENT, FAMILY, DOCTOR, ADMIN
    required String firstName,
    required String lastName,
    String? dateOfBirth,
  }) async {
    try {
      final data = {
        'username': username,
        'email': email,
        'phone_number': phoneNumber,
        'password': password,
        'password_confirm': passwordConfirm,
        'user_type': userType,
        'first_name': firstName,
        'last_name': lastName,
        if (dateOfBirth != null) 'date_of_birth': dateOfBirth,
      };

      final response = await _api.post('/api/v1/auth/register/', data: data);

      // Auto-save tokens after registration
      final tokens = response.data['tokens'];
      if (tokens != null) {
        await _api.saveTokens(tokens['access'], tokens['refresh']);
      }

      return response.data;
    } catch (e) {
      throw _handleAuthError(e);
    }
  }

  // ==================== LOGIN ====================

  /// Login with username/email/phone and password
  /// POST /api/v1/auth/login/
  Future<Map<String, dynamic>> login({
    required String username,
    required String password,
  }) async {
    try {
      final data = {
        'username': username, // Can be username, email, or phone
        'password': password,
      };

      final response = await _api.post('/api/v1/auth/login/', data: data);

      // Save tokens
      final tokens = response.data['tokens'];
      if (tokens != null) {
        await _api.saveTokens(tokens['access'], tokens['refresh']);
      }

      return response.data;
    } catch (e) {
      throw _handleAuthError(e);
    }
  }

  // ==================== LOGOUT ====================

  /// Logout and blacklist refresh token
  /// POST /api/v1/auth/logout/
  Future<void> logout() async {
    try {
      // Get refresh token from storage
      final refreshToken = await _api.getRefreshToken();

      if (refreshToken != null) {
        try {
          await _api.post(
            '/api/v1/auth/logout/',
            data: {'refresh': refreshToken},
          );
        } catch (e) {
          // Ignore server errors during logout
          print('Logout API error (ignored): $e');
        }
      }

      // Always clear local tokens
      await _api.clearTokens();
    } catch (e) {
      // Always clear local tokens even if API fails
      await _api.clearTokens();
      throw Exception('Logout failed: $e');
    }
  }

  // ==================== TOKEN REFRESH ====================

  /// Refresh access token using refresh token
  /// POST /api/v1/auth/token/refresh/
  Future<Map<String, dynamic>> refreshToken() async {
    try {
      final refreshToken = await _api.getRefreshToken();

      if (refreshToken == null) {
        throw Exception('No refresh token available');
      }

      final response = await _api.post(
        '/api/v1/auth/token/refresh/',
        data: {'refresh': refreshToken},
      );

      // Save new access token
      final newAccessToken = response.data['access'];
      if (newAccessToken != null) {
        await _api.saveAccessToken(newAccessToken);
      }

      return response.data;
    } catch (e) {
      throw Exception('Token refresh failed: $e');
    }
  }

  // ==================== USER PROFILE ====================

  /// Get current user profile
  /// GET /api/v1/auth/profile/
  Future<Map<String, dynamic>> getProfile() async {
    try {
      final response = await _api.get('/api/v1/auth/profile/');
      return response.data;
    } catch (e) {
      throw Exception('Failed to load profile: $e');
    }
  }

  /// Update current user profile
  /// PUT /api/v1/auth/profile/
  Future<Map<String, dynamic>> updateProfile(Map<String, dynamic> data) async {
    try {
      final response = await _api.put('/api/v1/auth/profile/', data: data);
      return response.data;
    } catch (e) {
      throw Exception('Failed to update profile: $e');
    }
  }

  /// Partially update current user profile
  /// PATCH /api/v1/auth/profile/
  Future<Map<String, dynamic>> patchProfile(Map<String, dynamic> data) async {
    try {
      final response = await _api.patch('/api/v1/auth/profile/', data: data);
      return response.data;
    } catch (e) {
      throw Exception('Failed to patch profile: $e');
    }
  }

  // ==================== HELPER METHODS ====================

  /// Save tokens to storage (convenience method)
  Future<void> saveTokens(String accessToken, String refreshToken) async {
    await _api.saveTokens(accessToken, refreshToken);
  }

  /// Clear stored tokens (convenience method)
  Future<void> clearTokens() async {
    await _api.clearTokens();
  }

  /// Check if user is authenticated (convenience method)
  Future<bool> isAuthenticated() async {
    final token = await _api.getAccessToken();
    return token != null && token.isNotEmpty;
  }

  /// Get current user info from stored profile (convenience method)
  Future<Map<String, dynamic>?> getCurrentUser() async {
    try {
      return await getProfile();
    } catch (e) {
      return null;
    }
  }

  // ==================== ERROR HANDLING ====================

  /// Handle authentication-specific errors
  String _handleAuthError(dynamic error) {
    if (error is DioException) {
      if (error.response != null) {
        final data = error.response?.data;

        // Handle specific error formats
        if (data is Map) {
          // Check for common error fields
          if (data.containsKey('detail')) {
            return data['detail'];
          }
          if (data.containsKey('non_field_errors')) {
            final errors = data['non_field_errors'];
            if (errors is List && errors.isNotEmpty) {
              return errors[0];
            }
          }
          if (data.containsKey('username')) {
            return 'Username: ${data['username'][0]}';
          }
          if (data.containsKey('email')) {
            return 'Email: ${data['email'][0]}';
          }
          if (data.containsKey('phone_number')) {
            return 'Phone: ${data['phone_number'][0]}';
          }
          if (data.containsKey('password')) {
            return 'Password: ${data['password'][0]}';
          }
        }

        return 'Authentication error: ${error.response?.statusCode}';
      }

      // Network errors
      if (error.type == DioExceptionType.connectionTimeout ||
          error.type == DioExceptionType.receiveTimeout) {
        return 'Connection timeout. Please check your internet.';
      }

      if (error.type == DioExceptionType.unknown) {
        return 'Network error. Please check your connection.';
      }

      return 'Authentication failed. Please try again.';
    }

    return error.toString();
  }
}
