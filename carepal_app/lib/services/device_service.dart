import 'package:dio/dio.dart';
import 'api_service.dart';

/// Complete Device Service - Cloud Devices, Bluetooth, OAuth
/// Maps to backend/devices/views.py
class DeviceService {
  final ApiService _api = ApiService();

  // ==================== CLOUD PROVIDERS ====================

  /// Get all cloud providers (Fitbit, Google Fit, etc.)
  /// GET /api/v1/devices/cloud-providers/
  Future<Map<String, dynamic>> getCloudProviders({
    int page = 1,
    int pageSize = 20,
  }) async {
    try {
      final response = await _api.get(
        '/api/v1/devices/cloud-providers/',
        queryParameters: {'page': page, 'page_size': pageSize},
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to load cloud providers: $e');
    }
  }

  /// Get a single cloud provider
  /// GET /api/v1/devices/cloud-providers/{id}/
  Future<Map<String, dynamic>> getCloudProvider(int id) async {
    try {
      final response = await _api.get('/api/v1/devices/cloud-providers/$id/');
      return response.data;
    } catch (e) {
      throw Exception('Failed to load cloud provider: $e');
    }
  }

  // ==================== CLOUD CREDENTIALS ====================

  /// Get cloud API credentials
  /// GET /api/v1/devices/cloud-credentials/
  Future<Map<String, dynamic>> getCloudCredentials({
    int? patientId,
    int? providerId,
    String? status,
    int page = 1,
    int pageSize = 20,
  }) async {
    try {
      final queryParams = <String, dynamic>{
        'page': page,
        'page_size': pageSize,
        if (patientId != null) 'patient': patientId,
        if (providerId != null) 'provider': providerId,
        if (status != null) 'status': status,
      };

      final response = await _api.get(
        '/api/v1/devices/cloud-credentials/',
        queryParameters: queryParams,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to load cloud credentials: $e');
    }
  }

  /// Get a single cloud credential
  /// GET /api/v1/devices/cloud-credentials/{id}/
  Future<Map<String, dynamic>> getCloudCredential(int id) async {
    try {
      final response = await _api.get('/api/v1/devices/cloud-credentials/$id/');
      return response.data;
    } catch (e) {
      throw Exception('Failed to load cloud credential: $e');
    }
  }

  /// Create cloud credential
  /// POST /api/v1/devices/cloud-credentials/
  Future<Map<String, dynamic>> createCloudCredential(
    Map<String, dynamic> data,
  ) async {
    try {
      final response = await _api.post(
        '/api/v1/devices/cloud-credentials/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to create cloud credential: $e');
    }
  }

  /// Update cloud credential
  /// PUT /api/v1/devices/cloud-credentials/{id}/
  Future<Map<String, dynamic>> updateCloudCredential(
    int id,
    Map<String, dynamic> data,
  ) async {
    try {
      final response = await _api.put(
        '/api/v1/devices/cloud-credentials/$id/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to update cloud credential: $e');
    }
  }

  /// Delete cloud credential
  /// DELETE /api/v1/devices/cloud-credentials/{id}/
  Future<void> deleteCloudCredential(int id) async {
    try {
      await _api.delete('/api/v1/devices/cloud-credentials/$id/');
    } catch (e) {
      throw Exception('Failed to delete cloud credential: $e');
    }
  }

  /// Trigger manual sync for cloud credential
  /// POST /api/v1/devices/cloud-credentials/{id}/sync_now/
  Future<Map<String, dynamic>> syncCloudCredential(int id) async {
    try {
      final response = await _api.post(
        '/api/v1/devices/cloud-credentials/$id/sync_now/',
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to sync cloud credential: $e');
    }
  }

  /// Revoke cloud credential
  /// POST /api/v1/devices/cloud-credentials/{id}/revoke/
  Future<Map<String, dynamic>> revokeCloudCredential(int id) async {
    try {
      final response = await _api.post(
        '/api/v1/devices/cloud-credentials/$id/revoke/',
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to revoke cloud credential: $e');
    }
  }

  // ==================== OAUTH FLOWS ====================

  /// Initiate Fitbit OAuth flow
  /// GET /api/v1/devices/cloud/fitbit/authorize/
  Future<Map<String, dynamic>> initiateFitbitOAuth({int? patientId}) async {
    try {
      final queryParams = <String, dynamic>{
        if (patientId != null) 'patient_id': patientId,
      };

      final response = await _api.get(
        '/api/v1/devices/cloud/fitbit/authorize/',
        queryParameters: queryParams,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to initiate Fitbit OAuth: $e');
    }
  }

  /// Initiate Google Fit OAuth flow
  /// GET /api/v1/devices/cloud/google-fit/authorize/
  Future<Map<String, dynamic>> initiateGoogleFitOAuth({int? patientId}) async {
    try {
      final queryParams = <String, dynamic>{
        if (patientId != null) 'patient_id': patientId,
      };

      final response = await _api.get(
        '/api/v1/devices/cloud/google-fit/authorize/',
        queryParameters: queryParams,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to initiate Google Fit OAuth: $e');
    }
  }

  // Note: OAuth callbacks are handled by backend redirect
  // Fitbit callback: GET /api/v1/devices/cloud/fitbit/callback/
  // Google Fit callback: GET /api/v1/devices/cloud/google-fit/callback/

  // ==================== BLUETOOTH DEVICES ====================

  /// Get Bluetooth devices
  /// GET /api/v1/devices/bluetooth/
  Future<Map<String, dynamic>> getBluetoothDevices({
    int? patientId,
    String? deviceType,
    bool? isActive,
    int page = 1,
    int pageSize = 20,
  }) async {
    try {
      final queryParams = <String, dynamic>{
        'page': page,
        'page_size': pageSize,
        if (patientId != null) 'patient': patientId,
        if (deviceType != null) 'device_type': deviceType,
        if (isActive != null) 'is_active': isActive,
      };

      final response = await _api.get(
        '/api/v1/devices/bluetooth/',
        queryParameters: queryParams,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to load Bluetooth devices: $e');
    }
  }

  /// Get a single Bluetooth device
  /// GET /api/v1/devices/bluetooth/{id}/
  Future<Map<String, dynamic>> getBluetoothDevice(int id) async {
    try {
      final response = await _api.get('/api/v1/devices/bluetooth/$id/');
      return response.data;
    } catch (e) {
      throw Exception('Failed to load Bluetooth device: $e');
    }
  }

  /// Create Bluetooth device
  /// POST /api/v1/devices/bluetooth/
  Future<Map<String, dynamic>> createBluetoothDevice(
    Map<String, dynamic> data,
  ) async {
    try {
      final response = await _api.post(
        '/api/v1/devices/bluetooth/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to create Bluetooth device: $e');
    }
  }

  /// Update Bluetooth device
  /// PUT /api/v1/devices/bluetooth/{id}/
  Future<Map<String, dynamic>> updateBluetoothDevice(
    int id,
    Map<String, dynamic> data,
  ) async {
    try {
      final response = await _api.put(
        '/api/v1/devices/bluetooth/$id/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to update Bluetooth device: $e');
    }
  }

  /// Delete Bluetooth device
  /// DELETE /api/v1/devices/bluetooth/{id}/
  Future<void> deleteBluetoothDevice(int id) async {
    try {
      await _api.delete('/api/v1/devices/bluetooth/$id/');
    } catch (e) {
      throw Exception('Failed to delete Bluetooth device: $e');
    }
  }

  /// Ingest data from Bluetooth device (called by Flutter app)
  /// POST /api/v1/devices/bluetooth/ingest_data/
  Future<Map<String, dynamic>> ingestBluetoothData({
    required int dataSourceId,
    required String sessionId,
    required List<Map<String, dynamic>> readings,
    int? batteryLevel,
    String? firmwareVersion,
  }) async {
    try {
      final data = {
        'data_source_id': dataSourceId,
        'session_id': sessionId,
        'readings': readings,
        if (batteryLevel != null) 'battery_level': batteryLevel,
        if (firmwareVersion != null) 'firmware_version': firmwareVersion,
      };

      final response = await _api.post(
        '/api/v1/devices/bluetooth/ingest_data/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to ingest Bluetooth data: $e');
    }
  }

  /// End Bluetooth session
  /// POST /api/v1/devices/bluetooth/{id}/end_session/
  Future<Map<String, dynamic>> endBluetoothSession(
    int id, {
    required String sessionId,
  }) async {
    try {
      final data = {'session_id': sessionId};

      final response = await _api.post(
        '/api/v1/devices/bluetooth/$id/end_session/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to end Bluetooth session: $e');
    }
  }

  // ==================== DEVICE SYNC LOGS ====================

  /// Get device sync logs
  /// GET /api/v1/devices/sync-logs/
  Future<Map<String, dynamic>> getSyncLogs({
    int? dataSourceId,
    String? status,
    String? syncType,
    int page = 1,
    int pageSize = 20,
  }) async {
    try {
      final queryParams = <String, dynamic>{
        'page': page,
        'page_size': pageSize,
        if (dataSourceId != null) 'data_source': dataSourceId,
        if (status != null) 'status': status,
        if (syncType != null) 'sync_type': syncType,
      };

      final response = await _api.get(
        '/api/v1/devices/sync-logs/',
        queryParameters: queryParams,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to load sync logs: $e');
    }
  }

  /// Get a single sync log
  /// GET /api/v1/devices/sync-logs/{id}/
  Future<Map<String, dynamic>> getSyncLog(int id) async {
    try {
      final response = await _api.get('/api/v1/devices/sync-logs/$id/');
      return response.data;
    } catch (e) {
      throw Exception('Failed to load sync log: $e');
    }
  }

  // ==================== DATA CONFLICTS ====================

  /// Get data conflicts
  /// GET /api/v1/devices/conflicts/
  Future<Map<String, dynamic>> getDataConflicts({
    int? patientId,
    String? resolutionStatus,
    int page = 1,
    int pageSize = 20,
  }) async {
    try {
      final queryParams = <String, dynamic>{
        'page': page,
        'page_size': pageSize,
        if (patientId != null) 'patient': patientId,
        if (resolutionStatus != null) 'resolution_status': resolutionStatus,
      };

      final response = await _api.get(
        '/api/v1/devices/conflicts/',
        queryParameters: queryParams,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to load data conflicts: $e');
    }
  }

  /// Get a single data conflict
  /// GET /api/v1/devices/conflicts/{id}/
  Future<Map<String, dynamic>> getDataConflict(int id) async {
    try {
      final response = await _api.get('/api/v1/devices/conflicts/$id/');
      return response.data;
    } catch (e) {
      throw Exception('Failed to load data conflict: $e');
    }
  }

  // ==================== DEVICE STATUS ====================

  /// Get overall device status
  /// GET /api/v1/devices/status/
  Future<List<dynamic>> getDeviceStatus({int? patientId}) async {
    try {
      final queryParams = <String, dynamic>{
        if (patientId != null) 'patient_id': patientId,
      };

      final response = await _api.get(
        '/api/v1/devices/status/',
        queryParameters: queryParams,
      );
      return response.data as List;
    } catch (e) {
      throw Exception('Failed to load device status: $e');
    }
  }
}
