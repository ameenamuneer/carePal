import 'package:dio/dio.dart';
import 'api_service.dart';

class AuthService {
  final ApiService _api = ApiService();

  Future<Map<String, dynamic>> register({
    required String username,
    required String email,
    required String phoneNumber,
    required String password,
    required String passwordConfirm,
    required String userType, // FAMILY or DOCTOR
    required String firstName,
    required String lastName,
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
      };

      final response = await _api.post('/api/v1/auth/register/', data: data);

      final tokens = response.data['tokens'];
      if (tokens != null) {
        await _api.saveTokens(tokens['access'], tokens['refresh']);
      }

      return response.data;
    } catch (e) {
      throw _handleAuthError(e);
    }
  }

  Future<Map<String, dynamic>> login({
    required String username,
    required String password,
  }) async {
    try {
      final data = {
        'username': username,
        'password': password,
      };

      final response = await _api.post('/api/v1/auth/login/', data: data);

      final tokens = response.data['tokens'];
      if (tokens != null) {
        await _api.saveTokens(tokens['access'], tokens['refresh']);
      }

      return response.data;
    } catch (e) {
      throw _handleAuthError(e);
    }
  }

  Future<void> logout() async {
    try {
      final refreshToken = await _api.getRefreshToken();
      if (refreshToken != null) {
        try {
          await _api.post(
            '/api/v1/auth/logout/',
            data: {'refresh': refreshToken},
          );
        } catch (e) {
          print('Logout API error (ignored): $e');
        }
      }
      await _api.clearTokens();
    } catch (e) {
      await _api.clearTokens();
      throw Exception('Logout failed: $e');
    }
  }

  Future<Map<String, dynamic>> getProfile() async {
    try {
      final response = await _api.get('/api/v1/auth/profile/');
      return response.data;
    } catch (e) {
      throw Exception('Failed to load profile: $e');
    }
  }

  Future<void> saveTokens(String accessToken, String refreshToken) async {
    await _api.saveTokens(accessToken, refreshToken);
  }

  Future<void> clearTokens() async {
    await _api.clearTokens();
  }

  Future<bool> isAuthenticated() async {
    final token = await _api.getAccessToken();
    return token != null && token.isNotEmpty;
  }

  Future<Map<String, dynamic>?> getCurrentUser() async {
    try {
      return await getProfile();
    } catch (e) {
      return null;
    }
  }

  String _handleAuthError(dynamic error) {
    if (error is DioException) {
      if (error.response != null) {
        final data = error.response?.data;
        if (data is Map) {
          if (data.containsKey('detail')) return data['detail'];
          if (data.containsKey('non_field_errors')) {
            final errors = data['non_field_errors'];
            if (errors is List && errors.isNotEmpty) return errors[0];
          }
          if (data.containsKey('username')) return 'Username: ${data['username'][0]}';
          if (data.containsKey('email')) return 'Email: ${data['email'][0]}';
          if (data.containsKey('phone_number')) return 'Phone: ${data['phone_number'][0]}';
          if (data.containsKey('password')) return 'Password: ${data['password'][0]}';
        }
        return 'Authentication error: ${error.response?.statusCode}';
      }
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
