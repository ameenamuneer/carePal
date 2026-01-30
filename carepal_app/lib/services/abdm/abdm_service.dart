import '../api_service.dart';

class AbdmService {
  final ApiService _api = ApiService();
  final String _basePath = '/api/v1/abdm';

  // ==================== REGISTRATION ENDPOINTS ====================

  // Step 1: Initiate Registration
  Future<String> initiateRegistration(String mobile) async {
    try {
      final response = await _api.post(
        '$_basePath/registration/init/',
        data: {'mobile': mobile},
      );

      if (response.statusCode == 200) {
        return response.data['txn_id'];
      } else {
        throw Exception(response.data['error'] ?? 'Registration failed');
      }
    } catch (e) {
      throw Exception('Network error: $e');
    }
  }

  // Step 2: Verify OTP
  Future<Map<String, dynamic>> verifyOtp(String txnId, String otp) async {
    try {
      final response = await _api.post(
        '$_basePath/registration/verify/',
        data: {'txn_id': txnId, 'otp': otp},
      );

      if (response.statusCode == 200) {
        return response.data;
      } else {
        throw Exception(response.data['error'] ?? 'OTP verification failed');
      }
    } catch (e) {
      throw Exception('Network error: $e');
    }
  }

  // Step 3: Create ABHA Address
  Future<Map<String, dynamic>> createAbhaAddress(
    String txnId,
    String abhaAddress,
  ) async {
    try {
      final response = await _api.post(
        '$_basePath/registration/create/',
        data: {'txn_id': txnId, 'abha_address': abhaAddress},
      );

      if (response.statusCode == 201 || response.statusCode == 200) {
        return response.data;
      } else {
        throw Exception(response.data['error'] ?? 'ABHA creation failed');
      }
    } catch (e) {
      throw Exception('Network error: $e');
    }
  }

  // ==================== LOGIN ENDPOINTS ====================

  // Step 1: Initiate Login
  Future<String> initiateLogin(String mobile) async {
    try {
      final response = await _api.post(
        '$_basePath/login/init/',
        data: {'mobile': mobile},
      );

      if (response.statusCode == 200) {
        return response.data['txn_id'];
      } else {
        throw Exception(response.data['error'] ?? 'Login initiation failed');
      }
    } catch (e) {
      throw Exception('Network error: $e');
    }
  }

  // Step 2: Verify Login OTP
  Future<Map<String, dynamic>> verifyLoginOtp(String txnId, String otp) async {
    try {
      final response = await _api.post(
        '$_basePath/login/verify/',
        data: {'txn_id': txnId, 'otp': otp},
      );

      if (response.statusCode == 200) {
        return response.data;
      } else {
        throw Exception(response.data['error'] ?? 'Login verification failed');
      }
    } catch (e) {
      throw Exception('Network error: $e');
    }
  }

  // Step 3: Complete Login (select ABHA address)
  Future<Map<String, dynamic>> completeLogin(
    String txnId,
    String abhaAddress,
  ) async {
    try {
      final response = await _api.post(
        '$_basePath/login/complete/',
        data: {'txn_id': txnId, 'abha_address': abhaAddress},
      );

      if (response.statusCode == 200) {
        return response.data;
      } else {
        throw Exception(response.data['error'] ?? 'Login completion failed');
      }
    } catch (e) {
      throw Exception('Network error: $e');
    }
  }

  // ==================== PHR ONBOARDING (DISCOVERY & LINKING) ====================

  // Step 1: Discover Care Contexts
  Future<Map<String, dynamic>> discoverCareContexts({
    required String hipId,
    required String refId,
  }) async {
    try {
      final response = await _api.post(
        '$_basePath/care-contexts/discover',
        data: {'hip_id': hipId, 'ref_id': refId},
      );

      if (response.statusCode == 200) {
        return response.data;
      } else {
        throw Exception(response.data['error'] ?? 'Discovery failed');
      }
    } catch (e) {
      throw Exception('Discovery error: $e');
    }
  }

  // Step 2: Initiate Linking
  Future<String> initiateLinking({
    required String txnId,
    required Map<String, dynamic> patient,
    required List<dynamic> careContexts,
  }) async {
    try {
      final response = await _api.post(
        '$_basePath/care-contexts/link/init',
        data: {
          'txn_id': txnId,
          'patient': patient,
          'care_contexts': careContexts,
        },
      );

      if (response.statusCode == 200) {
        return response.data['txn_id'] ?? txnId;
      } else {
        throw Exception(response.data['error'] ?? 'Link init failed');
      }
    } catch (e) {
      throw Exception('Link init error: $e');
    }
  }

  // Step 3: Confirm Linking
  Future<bool> confirmLinking({
    required String txnId,
    required String otp,
  }) async {
    try {
      final response = await _api.post(
        '$_basePath/care-contexts/link/confirm',
        data: {'txn_id': txnId, 'otp': otp},
      );

      if (response.statusCode == 200) {
        return true;
      } else {
        throw Exception(response.data['error'] ?? 'Link confirm failed');
      }
    } catch (e) {
      throw Exception('Link confirm error: $e');
    }
  }

  // ==================== REQUESTS (SUBSCRIPTIONS) ====================

  Future<Map<String, dynamic>> getRequests({
    String status = 'requested',
    String type = 'all',
  }) async {
    try {
      final response = await _api.get(
        '$_basePath/requests',
        queryParameters: {'status': status, 'type': type},
      );

      if (response.statusCode == 200) {
        return response.data;
      } else {
        throw Exception(response.data['error'] ?? 'Fetch requests failed');
      }
    } catch (e) {
      throw Exception('Fetch requests error: $e');
    }
  }

  // ==================== FHIR INTEGRATION ====================

  // Get PHR/FHIR Bundle for a specific vital
  Future<Map<String, dynamic>> getFhirBundle(int vitalId) async {
    try {
      // Note: We are using a new endpoint for this
      final response = await _api.get('/api/v1/fhir/vitals/$vitalId/export/');

      if (response.statusCode == 200) {
        return response.data;
      } else {
        throw Exception(
          response.data['error'] ?? 'Failed to fetch FHIR bundle',
        );
      }
    } catch (e) {
      throw Exception('FHIR export error: $e');
    }
  }
}
