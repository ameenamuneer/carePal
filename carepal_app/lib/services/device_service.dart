import 'api_service.dart';
import '../models/device.dart';

class DeviceService {
  final ApiService _api = ApiService();

  // Get device status
  Future<List<DeviceStatus>> getDeviceStatus() async {
    try {
      final response = await _api.get('/api/v1/devices/status/');
      final results = response.data as List;
      return results.map((json) => DeviceStatus.fromJson(json)).toList();
    } catch (e) {
      throw Exception('Failed to load devices: $e');
    }
  }

  // Ingest Bluetooth data
  Future<Map<String, dynamic>> ingestBluetoothData({
    required String sessionId,
    required int dataSourceId,
    required DateTime connectedAt,
    required List<Map<String, dynamic>> readings,
    int? batteryLevel,
    int? signalStrength,
  }) async {
    try {
      final data = {
        'session_id': sessionId,
        'data_source_id': dataSourceId,
        'connected_at': connectedAt.toIso8601String(),
        'readings': readings,
        if (batteryLevel != null) 'battery_level': batteryLevel,
        if (signalStrength != null) 'signal_strength': signalStrength,
      };

      final response = await _api.post(
        '/api/v1/devices/bluetooth/ingest/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to ingest data: $e');
    }
  }

  // End Bluetooth session
  Future<void> endBluetoothSession(int deviceId, String sessionId) async {
    try {
      await _api.post(
        '/api/v1/devices/bluetooth/$deviceId/end_session/',
        data: {'session_id': sessionId},
      );
    } catch (e) {
      throw Exception('Failed to end session: $e');
    }
  }
}
