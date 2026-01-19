import 'package:dio/dio.dart';
import 'api_service.dart';

class AuthService {
  final ApiService _apiService = ApiService();

  Future<Map<String, dynamic>> login(String username, String password) async {
    try {
      final response = await _apiService.client.post(
        '/auth/login/',
        data: {'username': username, 'password': password},
      );
      return response.data;
    } on DioException catch (e) {
      throw _handleError(e);
    }
  }

  Future<Map<String, dynamic>> register(Map<String, dynamic> userData) async {
    try {
      final response = await _apiService.client.post(
        '/auth/register/',
        data: userData,
      );
      return response.data;
    } on DioException catch (e) {
      throw _handleError(e);
    }
  }

  Future<void> logout(String refreshToken) async {
    try {
      await _apiService.client.post(
        '/auth/logout/',
        data: {'refresh': refreshToken},
      );
      await _apiService.clearTokens();
    } on DioException catch (e) {
      // Even if API fails, clear local tokens
      await _apiService.clearTokens();
      throw _handleError(e);
    }
  }

  Future<Map<String, dynamic>> getProfile() async {
    try {
      final response = await _apiService.client.get('/auth/profile/');
      return response.data;
    } on DioException catch (e) {
      throw _handleError(e);
    }
  }

  // Helper to save tokens via ApiService
  Future<void> saveTokens(String access, String refresh) async {
    await _apiService.saveTokens(access, refresh);
  }

  String _handleError(DioException e) {
    if (e.response != null) {
      return e.response?.data['detail'] ??
          e.response?.data['non_field_errors']?[0] ??
          'An validation error occurred';
    }
    return 'Connection error. Please check your internet.';
  }
}
