import 'api_service.dart';
import '../models/medication.dart';

class MedicationService {
  final ApiService _api = ApiService();

  // Get today's medication schedule
  Future<List<MedicationSchedule>> getTodaysSchedule() async {
    try {
      final response = await _api.get('/api/v1/medications/adherence/today/');
      final List<dynamic> data = response.data;

      return data.map((json) {
        // Construct Medication object from flat data
        final medication = Medication(
          id: json['medication_id'],
          patientId: 0, // Not provided in flat response, using 0 as placeholder
          medicationName: json['medication_name'],
          dosage: json['dosage'],
          instructions: json['instructions'] ?? '',
          form: json['form'] ?? '',
          frequency: '', // Not provided
          route: '', // Not provided
          startDate: DateTime.now(), // Placeholder
          status: 'ACTIVE',
        );

        return MedicationSchedule(
          id: json['adherence_id'],
          medication: medication,
          scheduledTime: DateTime.parse(json['scheduled_time']),
          status: json['status'],
          takenAt: json['actual_datetime'] != null
              ? DateTime.parse(json['actual_datetime'])
              : null,
        );
      }).toList();
    } catch (e) {
      print('Error fetching today\'s schedule: $e');
      return [];
    }
  }

  // Get all medications
  Future<List<Medication>> getMedications({String? status}) async {
    try {
      final queryParams = status != null ? {'status': status} : null;
      final response = await _api.get(
        '/api/v1/medications/medications/',
        queryParameters: queryParams,
      );
      final results = response.data['results'] as List;
      return results.map((json) => Medication.fromJson(json)).toList();
    } catch (e) {
      throw Exception('Failed to load medications: $e');
    }
  }

  // Log medication adherence
  Future<MedicationAdherence> logAdherence({
    required int medicationId,
    required String status, // 'TAKEN', 'MISSED', 'SKIPPED'
    DateTime? takenAt,
    String? notes,
  }) async {
    try {
      final data = {
        'medication': medicationId,
        'status': status,
        'taken_at': (takenAt ?? DateTime.now()).toIso8601String(),
        if (notes != null) 'notes': notes,
      };

      final response = await _api.post(
        '/api/v1/medications/adherence/log/',
        data: data,
      );
      return MedicationAdherence.fromJson(response.data);
    } catch (e) {
      throw Exception('Failed to log adherence: $e');
    }
  }

  // Get adherence history
  Future<List<MedicationAdherence>> getAdherenceHistory({
    int? medicationId,
    int days = 30,
  }) async {
    try {
      final queryParams = <String, dynamic>{
        'days': days,
        if (medicationId != null) 'medication': medicationId,
      };

      final response = await _api.get(
        '/api/v1/medications/adherence/',
        queryParameters: queryParams,
      );
      final results = response.data['results'] as List;
      return results.map((json) => MedicationAdherence.fromJson(json)).toList();
    } catch (e) {
      throw Exception('Failed to load adherence: $e');
    }
  }

  // Get adherence rate
  Future<double> getAdherenceRate(int days) async {
    try {
      final response = await _api.get(
        '/api/v1/medications/adherence-rate/',
        queryParameters: {'days': days},
      );
      return (response.data['adherence_rate'] as num).toDouble();
    } catch (e) {
      throw Exception('Failed to get adherence rate: $e');
    }
  }
}
