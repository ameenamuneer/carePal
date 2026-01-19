import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class ApiService {
  late Dio _dio;
  final FlutterSecureStorage _storage = const FlutterSecureStorage();

  // Base URL for API - Use localhost for web/docker dev
  // In production, this would be an environment variable
  static const String baseUrl = 'http://localhost:8000/api/v1';

  ApiService() {
    _dio = Dio(
      BaseOptions(
        baseUrl: baseUrl,
        connectTimeout: const Duration(seconds: 15),
        receiveTimeout: const Duration(seconds: 15),
        headers: {'Content-Type': 'application/json'},
      ),
    );

    _setupInterceptors();
  }

  // Getter for the dio instance
  Dio get client => _dio;

  void _setupInterceptors() {
    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) async {
          // Add Access Token to Header
          final token = await _storage.read(key: 'access_token');
          if (token != null) {
            options.headers['Authorization'] = 'Bearer $token';
          }
          return handler.next(options);
        },
        onError: (DioException e, handler) async {
          // Handle 401 Unauthorized - Token Refresh Logic
          if (e.response?.statusCode == 401) {
            try {
              final refreshToken = await _storage.read(key: 'refresh_token');
              if (refreshToken != null) {
                // Attempt refresh
                final refreshResponse = await Dio(
                  BaseOptions(baseUrl: baseUrl),
                ).post('/auth/token/refresh/', data: {'refresh': refreshToken});

                if (refreshResponse.statusCode == 200) {
                  // Save new tokens
                  final newAccess = refreshResponse.data['access'];
                  // Some backends might return a new refresh token too
                  final newRefresh = refreshResponse.data['refresh'];

                  await _storage.write(key: 'access_token', value: newAccess);
                  if (newRefresh != null) {
                    await _storage.write(
                      key: 'refresh_token',
                      value: newRefresh,
                    );
                  }

                  // Retry original request
                  final opts = e.requestOptions;
                  opts.headers['Authorization'] = 'Bearer $newAccess';

                  final clonedRequest = await _dio.fetch(opts);
                  return handler.resolve(clonedRequest);
                }
              }
            } catch (refreshError) {
              // Refresh failed - User needs to login again
              // In a real app, you might trigger a logout event stream here
              await _storage.deleteAll();
            }
          }
          return handler.next(e);
        },
      ),
    );
  }

  Future<void> saveTokens(String access, String refresh) async {
    await _storage.write(key: 'access_token', value: access);
    await _storage.write(key: 'refresh_token', value: refresh);
  }

  Future<void> clearTokens() async {
    await _storage.deleteAll();
  }
}
