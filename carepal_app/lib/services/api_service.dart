import 'dart:convert';
import 'package:dio/dio.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../core/config.dart';

class ApiService {
  static final ApiService _instance = ApiService._internal();
  factory ApiService() => _instance;
  ApiService._internal();

  late Dio _dio;
  // Separate client without interceptors for token refresh, so a rejected
  // refresh can never re-enter the 401 handler and loop.
  late Dio _refreshDio;
  String? _accessToken;
  String? _refreshToken;
  bool _tokensLoaded = false;
  // Single in-flight refresh shared by concurrent callers: the backend rotates
  // and blacklists refresh tokens, so two parallel refreshes would race.
  Future<bool>? _refreshing;

  /// Called when the session can no longer be renewed (refresh token expired
  /// or rejected). AuthProvider uses it to return to the login screen.
  void Function()? onSessionExpired;

  static const String baseUrl = kBaseUrl;

  // Auth endpoints never carry (or refresh) the access token.
  static const _authPaths = [
    '/api/v1/auth/login/',
    '/api/v1/auth/register/',
    '/api/v1/auth/token/refresh/',
  ];

  BaseOptions _baseOptions() => BaseOptions(
        baseUrl: baseUrl,
        connectTimeout: const Duration(seconds: 30),
        receiveTimeout: const Duration(seconds: 30),
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
      );

  void initialize() {
    _dio = Dio(_baseOptions());
    _refreshDio = Dio(_baseOptions());

    // Add interceptors
    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) async {
          // Attach a valid access token, refreshing it first if it has expired.
          if (!_authPaths.contains(options.path)) {
            final token = await getValidAccessToken();
            if (token != null) {
              options.headers['Authorization'] = 'Bearer $token';
            }
          }
          return handler.next(options);
        },
        onError: (error, handler) async {
          // 401 despite the expiry check (e.g. clock skew): refresh and retry once.
          final opts = error.requestOptions;
          if (error.response?.statusCode == 401 &&
              !_authPaths.contains(opts.path) &&
              opts.extra['auth_retried'] != true) {
            if (await refreshAccessToken()) {
              opts.headers['Authorization'] = 'Bearer $_accessToken';
              opts.extra['auth_retried'] = true;
              try {
                return handler.resolve(await _dio.fetch(opts));
              } on DioException catch (e) {
                return handler.next(e);
              }
            }
          }
          return handler.next(error);
        },
      ),
    );
  }

  // ==================== TOKEN LIFECYCLE ====================

  /// Expiry (seconds since epoch) from a JWT's payload, or null if unreadable.
  static int? _jwtExpiry(String? token) {
    if (token == null) return null;
    final parts = token.split('.');
    if (parts.length != 3) return null;
    try {
      final payload = jsonDecode(
        utf8.decode(base64Url.decode(base64Url.normalize(parts[1]))),
      );
      final exp = payload['exp'];
      return exp is num ? exp.toInt() : null;
    } catch (_) {
      return null;
    }
  }

  static bool _expiresWithin(String? token, Duration margin) {
    final exp = _jwtExpiry(token);
    if (exp == null) return true;
    final now = DateTime.now().millisecondsSinceEpoch ~/ 1000;
    return exp - now <= margin.inSeconds;
  }

  Future<void> _ensureTokensLoaded() async {
    if (!_tokensLoaded) await loadTokens();
  }

  /// True if a saved login can still be renewed (refresh token present and
  /// not expired). Checked locally, so it also works offline.
  Future<bool> hasSession() async {
    await _ensureTokensLoaded();
    return _refreshToken != null && !_expiresWithin(_refreshToken, Duration.zero);
  }

  /// An access token that is valid for at least another minute, refreshed
  /// first if needed. Returns null when there is no session. If the refresh
  /// fails for network reasons, the current (possibly expired) token is kept.
  Future<String?> getValidAccessToken() async {
    await _ensureTokensLoaded();
    if (_accessToken != null &&
        !_expiresWithin(_accessToken, const Duration(seconds: 60))) {
      return _accessToken;
    }
    if (_refreshToken == null) return null;
    await refreshAccessToken();
    return _accessToken;
  }

  /// Get a new access token with the refresh token. Concurrent calls share one
  /// request.
  Future<bool> refreshAccessToken() {
    return _refreshing ??= _doRefresh().whenComplete(() => _refreshing = null);
  }

  Future<bool> _doRefresh() async {
    await _ensureTokensLoaded();
    final refresh = _refreshToken;
    if (refresh == null) return false;
    try {
      final response = await _refreshDio.post(
        '/api/v1/auth/token/refresh/',
        data: {'refresh': refresh},
      );
      final access = response.data['access'] as String?;
      if (access == null) return false;
      // The backend rotates refresh tokens (the old one is blacklisted): keep
      // the new one. This also slides the session's expiry forward, so an app
      // in regular use stays logged in.
      final newRefresh = response.data['refresh'] as String? ?? refresh;
      await saveTokens(access, newRefresh);
      return true;
    } on DioException catch (e) {
      final code = e.response?.statusCode;
      if (code == 400 || code == 401) {
        // Refresh token expired, blacklisted, or the user is gone: the
        // session is over.
        await clearTokens();
        onSessionExpired?.call();
      }
      // Network errors keep the tokens: being offline must not log you out.
      return false;
    } catch (_) {
      return false;
    }
  }

  Future<void> saveTokens(String accessToken, String refreshToken) async {
    _accessToken = accessToken;
    _refreshToken = refreshToken;
    await _saveTokens(accessToken, refreshToken);
  }

  Future<void> _saveTokens(String accessToken, String refreshToken) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('access_token', accessToken);
    await prefs.setString('refresh_token', refreshToken);
  }

  Future<void> loadTokens() async {
    final prefs = await SharedPreferences.getInstance();
    _accessToken = prefs.getString('access_token');
    _refreshToken = prefs.getString('refresh_token');
    _tokensLoaded = true;
  }

  Future<void> clearTokens() async {
    _accessToken = null;
    _refreshToken = null;
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('access_token');
    await prefs.remove('refresh_token');
  }

  Future<String?> getAccessToken() async {
    if (_accessToken == null) {
      await loadTokens();
    }
    return _accessToken;
  }

  Future<String?> getRefreshToken() async {
    if (_refreshToken == null) {
      await loadTokens();
    }
    return _refreshToken;
  }

  Future<void> saveAccessToken(String token) async {
    _accessToken = token;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('access_token', token);
  }

  bool get hasValidToken => _accessToken != null;

  // HTTP Methods
  Future<Response> get(
    String path, {
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) {
    return _dio.get(path, queryParameters: queryParameters, options: options);
  }

  Future<Response> post(String path, {dynamic data, Options? options}) {
    return _dio.post(path, data: data, options: options);
  }

  Future<Response> put(String path, {dynamic data, Options? options}) {
    return _dio.put(path, data: data, options: options);
  }

  Future<Response> patch(String path, {dynamic data, Options? options}) {
    return _dio.patch(path, data: data, options: options);
  }

  Future<Response> delete(String path, {Options? options}) {
    return _dio.delete(path, options: options);
  }
}
