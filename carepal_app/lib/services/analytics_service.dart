import 'package:dio/dio.dart';
import 'api_service.dart';

/// Analytics Service - Complete implementation
/// Maps to backend/analytics/views.py endpoints
class AnalyticsService {
  final ApiService _api = ApiService();

  // ==================== DASHBOARDS ====================

  /// Get patient dashboard with comprehensive health overview
  /// GET /api/v1/analytics/dashboard/patient/
  Future<Map<String, dynamic>> getPatientDashboard({int? patientId}) async {
    try {
      final queryParams = <String, dynamic>{
        if (patientId != null) 'patient_id': patientId,
      };

      final response = await _api.get(
        '/api/v1/analytics/dashboard/patient/',
        queryParameters: queryParams,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to load patient dashboard: $e');
    }
  }

  /// Get family dashboard with patient overview
  /// GET /api/v1/analytics/dashboard/family/
  Future<Map<String, dynamic>> getFamilyDashboard({
    required int patientId,
  }) async {
    try {
      final queryParams = {'patient_id': patientId};

      final response = await _api.get(
        '/api/v1/analytics/dashboard/family/',
        queryParameters: queryParams,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to load family dashboard: $e');
    }
  }

  // ==================== HEALTH METRICS ====================

  /// Get health metrics
  /// GET /api/v1/analytics/metrics/
  Future<Map<String, dynamic>> getHealthMetrics({
    int? patientId,
    String? periodType,
    int page = 1,
    int pageSize = 20,
  }) async {
    try {
      final queryParams = <String, dynamic>{
        'page': page,
        'page_size': pageSize,
        if (patientId != null) 'patient': patientId,
        if (periodType != null) 'period_type': periodType,
      };

      final response = await _api.get(
        '/api/v1/analytics/metrics/',
        queryParameters: queryParams,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to load health metrics: $e');
    }
  }

  /// Get a single health metric
  /// GET /api/v1/analytics/metrics/{id}/
  Future<Map<String, dynamic>> getHealthMetric(int id) async {
    try {
      final response = await _api.get('/api/v1/analytics/metrics/$id/');
      return response.data;
    } catch (e) {
      throw Exception('Failed to load health metric: $e');
    }
  }

  /// Manually trigger metrics computation
  /// POST /api/v1/analytics/metrics/compute_now/
  Future<Map<String, dynamic>> computeMetricsNow({
    required int patientId,
    String? periodType,
    String? startDate,
    String? endDate,
  }) async {
    try {
      final data = {
        'patient_id': patientId,
        if (periodType != null) 'period_type': periodType,
        if (startDate != null) 'start_date': startDate,
        if (endDate != null) 'end_date': endDate,
      };

      final response = await _api.post(
        '/api/v1/analytics/metrics/compute_now/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to compute metrics: $e');
    }
  }

  // ==================== TREND ANALYSIS ====================

  /// Get trend analyses
  /// GET /api/v1/analytics/trends/
  Future<Map<String, dynamic>> getTrendAnalyses({
    int? patientId,
    String? analysisType,
    int page = 1,
    int pageSize = 20,
  }) async {
    try {
      final queryParams = <String, dynamic>{
        'page': page,
        'page_size': pageSize,
        if (patientId != null) 'patient': patientId,
        if (analysisType != null) 'analysis_type': analysisType,
      };

      final response = await _api.get(
        '/api/v1/analytics/trends/',
        queryParameters: queryParams,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to load trend analyses: $e');
    }
  }

  /// Get a single trend analysis
  /// GET /api/v1/analytics/trends/{id}/
  Future<Map<String, dynamic>> getTrendAnalysis(int id) async {
    try {
      final response = await _api.get('/api/v1/analytics/trends/$id/');
      return response.data;
    } catch (e) {
      throw Exception('Failed to load trend analysis: $e');
    }
  }

  // ==================== RISK SCORES ====================

  /// Get risk scores
  /// GET /api/v1/analytics/risk-scores/
  Future<Map<String, dynamic>> getRiskScores({
    int? patientId,
    String? riskType,
    String? riskCategory,
    bool? isActive,
    int page = 1,
    int pageSize = 20,
  }) async {
    try {
      final queryParams = <String, dynamic>{
        'page': page,
        'page_size': pageSize,
        if (patientId != null) 'patient': patientId,
        if (riskType != null) 'risk_type': riskType,
        if (riskCategory != null) 'risk_category': riskCategory,
        if (isActive != null) 'is_active': isActive,
      };

      final response = await _api.get(
        '/api/v1/analytics/risk-scores/',
        queryParameters: queryParams,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to load risk scores: $e');
    }
  }

  /// Get a single risk score
  /// GET /api/v1/analytics/risk-scores/{id}/
  Future<Map<String, dynamic>> getRiskScore(int id) async {
    try {
      final response = await _api.get('/api/v1/analytics/risk-scores/$id/');
      return response.data;
    } catch (e) {
      throw Exception('Failed to load risk score: $e');
    }
  }

  /// Get active risk scores for a patient
  /// GET /api/v1/analytics/risk-scores/active/
  Future<List<dynamic>> getActiveRiskScores({required int patientId}) async {
    try {
      final queryParams = {'patient_id': patientId};

      final response = await _api.get(
        '/api/v1/analytics/risk-scores/active/',
        queryParameters: queryParams,
      );
      return response.data as List;
    } catch (e) {
      throw Exception('Failed to load active risk scores: $e');
    }
  }

  // ==================== INSIGHTS ====================

  /// Get insight records
  /// GET /api/v1/analytics/insights/
  Future<Map<String, dynamic>> getInsights({
    int? patientId,
    String? insightType,
    String? insightCategory,
    bool? validationPassed,
    bool? requiresReview,
    int page = 1,
    int pageSize = 20,
  }) async {
    try {
      final queryParams = <String, dynamic>{
        'page': page,
        'page_size': pageSize,
        if (patientId != null) 'patient': patientId,
        if (insightType != null) 'insight_type': insightType,
        if (insightCategory != null) 'insight_category': insightCategory,
        if (validationPassed != null) 'validation_passed': validationPassed,
        if (requiresReview != null) 'requires_review': requiresReview,
      };

      final response = await _api.get(
        '/api/v1/analytics/insights/',
        queryParameters: queryParams,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to load insights: $e');
    }
  }

  /// Get a single insight record
  /// GET /api/v1/analytics/insights/{id}/
  Future<Map<String, dynamic>> getInsight(int id) async {
    try {
      final response = await _api.get('/api/v1/analytics/insights/$id/');
      return response.data;
    } catch (e) {
      throw Exception('Failed to load insight: $e');
    }
  }

  // ==================== HEALTH REPORTS ====================

  /// Get health reports
  /// GET /api/v1/analytics/reports/
  Future<Map<String, dynamic>> getHealthReports({
    int? patientId,
    String? reportType,
    String? status,
    int page = 1,
    int pageSize = 20,
  }) async {
    try {
      final queryParams = <String, dynamic>{
        'page': page,
        'page_size': pageSize,
        if (patientId != null) 'patient': patientId,
        if (reportType != null) 'report_type': reportType,
        if (status != null) 'status': status,
      };

      final response = await _api.get(
        '/api/v1/analytics/reports/',
        queryParameters: queryParams,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to load health reports: $e');
    }
  }

  /// Get a single health report
  /// GET /api/v1/analytics/reports/{id}/
  Future<Map<String, dynamic>> getHealthReport(int id) async {
    try {
      final response = await _api.get('/api/v1/analytics/reports/$id/');
      return response.data;
    } catch (e) {
      throw Exception('Failed to load health report: $e');
    }
  }

  /// Generate a new health report
  /// POST /api/v1/analytics/reports/generate/
  Future<Map<String, dynamic>> generateHealthReport({
    required int patientId,
    required String reportType,
    required String startDate,
    required String endDate,
    String? reportTitle,
    bool includeAiInsights = true,
    bool generatePdf = true,
    bool generateExcel = false,
    int? templateId,
  }) async {
    try {
      final data = {
        'patient_id': patientId,
        'report_type': reportType,
        'start_date': startDate,
        'end_date': endDate,
        if (reportTitle != null) 'report_title': reportTitle,
        'include_ai_insights': includeAiInsights,
        'generate_pdf': generatePdf,
        'generate_excel': generateExcel,
        if (templateId != null) 'template_id': templateId,
      };

      final response = await _api.post(
        '/api/v1/analytics/reports/generate/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to generate health report: $e');
    }
  }

  /// Download report as PDF
  /// GET /api/v1/analytics/reports/{id}/download_pdf/
  Future<Response> downloadReportPdf(int id) async {
    try {
      final response = await _api.get(
        '/api/v1/analytics/reports/$id/download_pdf/',
        options: Options(responseType: ResponseType.bytes),
      );
      return response;
    } catch (e) {
      throw Exception('Failed to download PDF: $e');
    }
  }

  /// Download report as Excel
  /// GET /api/v1/analytics/reports/{id}/download_excel/
  Future<Response> downloadReportExcel(int id) async {
    try {
      final response = await _api.get(
        '/api/v1/analytics/reports/$id/download_excel/',
        options: Options(responseType: ResponseType.bytes),
      );
      return response;
    } catch (e) {
      throw Exception('Failed to download Excel: $e');
    }
  }

  /// Create a health report
  /// POST /api/v1/analytics/reports/
  Future<Map<String, dynamic>> createHealthReport(
    Map<String, dynamic> data,
  ) async {
    try {
      final response = await _api.post(
        '/api/v1/analytics/reports/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to create health report: $e');
    }
  }

  /// Update a health report
  /// PUT /api/v1/analytics/reports/{id}/
  Future<Map<String, dynamic>> updateHealthReport(
    int id,
    Map<String, dynamic> data,
  ) async {
    try {
      final response = await _api.put(
        '/api/v1/analytics/reports/$id/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to update health report: $e');
    }
  }

  /// Partially update a health report
  /// PATCH /api/v1/analytics/reports/{id}/
  Future<Map<String, dynamic>> patchHealthReport(
    int id,
    Map<String, dynamic> data,
  ) async {
    try {
      final response = await _api.patch(
        '/api/v1/analytics/reports/$id/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to patch health report: $e');
    }
  }

  /// Delete a health report
  /// DELETE /api/v1/analytics/reports/{id}/
  Future<void> deleteHealthReport(int id) async {
    try {
      await _api.delete('/api/v1/analytics/reports/$id/');
    } catch (e) {
      throw Exception('Failed to delete health report: $e');
    }
  }

  // ==================== SCHEDULED REPORTS ====================

  /// Get scheduled reports
  /// GET /api/v1/analytics/scheduled-reports/
  Future<Map<String, dynamic>> getScheduledReports({
    int? patientId,
    String? frequency,
    bool? isActive,
    int page = 1,
    int pageSize = 20,
  }) async {
    try {
      final queryParams = <String, dynamic>{
        'page': page,
        'page_size': pageSize,
        if (patientId != null) 'patient': patientId,
        if (frequency != null) 'frequency': frequency,
        if (isActive != null) 'is_active': isActive,
      };

      final response = await _api.get(
        '/api/v1/analytics/scheduled-reports/',
        queryParameters: queryParams,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to load scheduled reports: $e');
    }
  }

  /// Get a single scheduled report
  /// GET /api/v1/analytics/scheduled-reports/{id}/
  Future<Map<String, dynamic>> getScheduledReport(int id) async {
    try {
      final response = await _api.get(
        '/api/v1/analytics/scheduled-reports/$id/',
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to load scheduled report: $e');
    }
  }

  /// Create a scheduled report
  /// POST /api/v1/analytics/scheduled-reports/
  Future<Map<String, dynamic>> createScheduledReport(
    Map<String, dynamic> data,
  ) async {
    try {
      final response = await _api.post(
        '/api/v1/analytics/scheduled-reports/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to create scheduled report: $e');
    }
  }

  /// Update a scheduled report
  /// PUT /api/v1/analytics/scheduled-reports/{id}/
  Future<Map<String, dynamic>> updateScheduledReport(
    int id,
    Map<String, dynamic> data,
  ) async {
    try {
      final response = await _api.put(
        '/api/v1/analytics/scheduled-reports/$id/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to update scheduled report: $e');
    }
  }

  /// Partially update a scheduled report
  /// PATCH /api/v1/analytics/scheduled-reports/{id}/
  Future<Map<String, dynamic>> patchScheduledReport(
    int id,
    Map<String, dynamic> data,
  ) async {
    try {
      final response = await _api.patch(
        '/api/v1/analytics/scheduled-reports/$id/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to patch scheduled report: $e');
    }
  }

  /// Delete a scheduled report
  /// DELETE /api/v1/analytics/scheduled-reports/{id}/
  Future<void> deleteScheduledReport(int id) async {
    try {
      await _api.delete('/api/v1/analytics/scheduled-reports/$id/');
    } catch (e) {
      throw Exception('Failed to delete scheduled report: $e');
    }
  }

  // ==================== REPORT TEMPLATES ====================

  /// Get report templates
  /// GET /api/v1/analytics/templates/
  Future<Map<String, dynamic>> getReportTemplates({
    String? reportType,
    bool? isDefault,
    bool? isActive,
    String? search,
    int page = 1,
    int pageSize = 50,
  }) async {
    try {
      final queryParams = <String, dynamic>{
        'page': page,
        'page_size': pageSize,
        if (reportType != null) 'report_type': reportType,
        if (isDefault != null) 'is_default': isDefault,
        if (isActive != null) 'is_active': isActive,
        if (search != null) 'search': search,
      };

      final response = await _api.get(
        '/api/v1/analytics/templates/',
        queryParameters: queryParams,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to load report templates: $e');
    }
  }

  /// Get a single report template
  /// GET /api/v1/analytics/templates/{id}/
  Future<Map<String, dynamic>> getReportTemplate(int id) async {
    try {
      final response = await _api.get('/api/v1/analytics/templates/$id/');
      return response.data;
    } catch (e) {
      throw Exception('Failed to load report template: $e');
    }
  }

  /// Create a report template
  /// POST /api/v1/analytics/templates/
  Future<Map<String, dynamic>> createReportTemplate(
    Map<String, dynamic> data,
  ) async {
    try {
      final response = await _api.post(
        '/api/v1/analytics/templates/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to create report template: $e');
    }
  }

  /// Update a report template
  /// PUT /api/v1/analytics/templates/{id}/
  Future<Map<String, dynamic>> updateReportTemplate(
    int id,
    Map<String, dynamic> data,
  ) async {
    try {
      final response = await _api.put(
        '/api/v1/analytics/templates/$id/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to update report template: $e');
    }
  }

  /// Partially update a report template
  /// PATCH /api/v1/analytics/templates/{id}/
  Future<Map<String, dynamic>> patchReportTemplate(
    int id,
    Map<String, dynamic> data,
  ) async {
    try {
      final response = await _api.patch(
        '/api/v1/analytics/templates/$id/',
        data: data,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to patch report template: $e');
    }
  }

  /// Delete a report template
  /// DELETE /api/v1/analytics/templates/{id}/
  Future<void> deleteReportTemplate(int id) async {
    try {
      await _api.delete('/api/v1/analytics/templates/$id/');
    } catch (e) {
      throw Exception('Failed to delete report template: $e');
    }
  }
}
