import 'package:flutter/material.dart';
import '../services/api_service.dart';

class AuthProvider with ChangeNotifier {
  final ApiService _apiService = ApiService();
  bool _isAuthenticated = false;
  bool _isLoading = false;

  bool get isAuthenticated => _isAuthenticated;
  bool get isLoading => _isLoading;

  Future<bool> login(String username, String password) async {
    _isLoading = true;
    notifyListeners();

    try {
      final response = await _apiService.client.post(
        '/users/token/',
        data: {'username': username, 'password': password},
      );

      if (response.statusCode == 200) {
        final data = response.data;
        await _apiService.saveTokens(data['access'], data['refresh']);
        _isAuthenticated = true;
        _isLoading = false;
        notifyListeners();
        return true;
      }
    } catch (e) {
      print('Login Error: $e');
    }

    _isLoading = false;
    notifyListeners();
    return false;
  }
}
