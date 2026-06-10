import '../models/activity_log.dart';
import 'api_service.dart';

class ActivityLogService {
  final ApiService _api = ApiService();

  Future<Map<String, dynamic>> fetchLogs({
    int? patientId,
    String? activityType,
    bool? isNotable,
    String? aiConfidence,
    String? dateFrom,
    String? dateTo,
    String? tags,
    String ordering = '-observed_at',
    int page = 1,
  }) async {
    final params = <String, dynamic>{
      'ordering': ordering,
      'page': page,
    };
    if (patientId != null) params['patient'] = patientId;
    if (activityType != null) params['activity_type'] = activityType;
    if (isNotable != null) params['is_notable'] = isNotable;
    if (aiConfidence != null) params['ai_confidence'] = aiConfidence;
    if (dateFrom != null) params['date_from'] = dateFrom;
    if (dateTo != null) params['date_to'] = dateTo;
    if (tags != null) params['tags'] = tags;

    final response = await _api.get(
      '/api/agent/activity-logs/',
      queryParameters: params,
    );

    final data = response.data as Map<String, dynamic>;
    final results = (data['results'] as List)
        .map((e) => ActivityLog.fromJson(e as Map<String, dynamic>))
        .toList();

    return {
      'count': data['count'] ?? 0,
      'next': data['next'],
      'results': results,
    };
  }
}
