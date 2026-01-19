import 'api_service.dart';
import '../models/vital_reading.dart';

class VitalsService {
  final ApiService _api = ApiService();

  // Get vitals readings with filters
  Future<List<VitalReading>> getReadings({
    String? vitalType,
    int days = 7,
    int? limit,
  }) async {
    try {
      final queryParams = <String, dynamic>{
        if (vitalType != null) 'vital_type': vitalType,
        'days': days,
        if (limit != null) 'limit': limit,
      };

      final response = await _api.get(
        '/api/v1/vitals/readings/',
        queryParameters: queryParams,
      );

      final results = response.data['results'] as List;
      return results.map((json) => VitalReading.fromJson(json)).toList();
    } catch (e) {
      throw Exception('Failed to load vitals: $e');
    }
  }

  // Get latest reading for specific vital type
  Future<VitalReading?> getLatestReading(String vitalCode) async {
    try {
      final readings = await getReadings(vitalType: vitalCode, limit: 1);
      return readings.isNotEmpty ? readings.first : null;
    } catch (e) {
      return null;
    }
  }

  // Create new vital reading (manual entry)
  Future<VitalReading> createReading({
    required int vitalTypeId,
    double? value,
    Map<String, dynamic>? values,
    required String unit,
    DateTime? measuredAt,
    String? notes,
  }) async {
    try {
      final data = {
        'vital_type': vitalTypeId,
        if (value != null) 'value': value,
        if (values != null) 'values': values,
        'unit': unit,
        'measured_at': (measuredAt ?? DateTime.now()).toIso8601String(),
        'source': 'MANUAL_ENTRY',
        if (notes != null) 'notes': notes,
      };

      final response = await _api.post('/api/v1/vitals/readings/', data: data);
      return VitalReading.fromJson(response.data);
    } catch (e) {
      throw Exception('Failed to create reading: $e');
    }
  }

  // Get vital types
  Future<List<VitalType>> getVitalTypes() async {
    try {
      final response = await _api.get('/api/v1/vitals/types/');
      final results = response.data['results'] as List;
      return results.map((json) => VitalType.fromJson(json)).toList();
    } catch (e) {
      throw Exception('Failed to load vital types: $e');
    }
  }

  // Get statistics for a vital type
  Future<Map<String, dynamic>> getVitalStats(String vitalCode, int days) async {
    try {
      final response = await _api.get(
        '/api/v1/vitals/stats/',
        queryParameters: {'vital_code': vitalCode, 'days': days},
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to load stats: $e');
    }
  }
}
