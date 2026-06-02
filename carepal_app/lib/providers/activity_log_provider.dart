import 'package:flutter/foundation.dart';
import '../models/activity_log.dart';
import '../services/activity_log_service.dart';

class ActivityLogProvider extends ChangeNotifier {
  final ActivityLogService _service = ActivityLogService();

  List<ActivityLog> _logs = [];
  bool _isLoading = false;
  String? _error;
  int _totalCount = 0;
  bool _hasMore = true;
  int _currentPage = 1;

  // Active filters
  String? _filterType;
  bool? _filterNotable;
  String? _filterDateFrom;
  String? _filterDateTo;
  String? _filterTags;

  List<ActivityLog> get logs => _logs;
  bool get isLoading => _isLoading;
  String? get error => _error;
  int get totalCount => _totalCount;
  bool get hasMore => _hasMore;
  String? get filterType => _filterType;
  bool? get filterNotable => _filterNotable;

  Future<void> loadLogs({bool reset = true}) async {
    if (reset) {
      _currentPage = 1;
      _logs = [];
      _hasMore = true;
    } else if (!_hasMore) {
      return;
    }

    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final result = await _service.fetchLogs(
        activityType: _filterType,
        isNotable: _filterNotable,
        dateFrom: _filterDateFrom,
        dateTo: _filterDateTo,
        tags: _filterTags,
        page: _currentPage,
      );

      final newLogs = result['results'] as List<ActivityLog>;
      _totalCount = result['count'] as int;
      _hasMore = result['next'] != null;
      _currentPage++;

      if (reset) {
        _logs = newLogs;
      } else {
        _logs = [..._logs, ...newLogs];
      }
    } catch (e) {
      _error = e.toString();
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  void setFilters({
    String? activityType,
    bool? isNotable,
    String? dateFrom,
    String? dateTo,
    String? tags,
  }) {
    _filterType = activityType;
    _filterNotable = isNotable;
    _filterDateFrom = dateFrom;
    _filterDateTo = dateTo;
    _filterTags = tags;
    loadLogs(reset: true);
  }

  void clearFilters() {
    _filterType = null;
    _filterNotable = null;
    _filterDateFrom = null;
    _filterDateTo = null;
    _filterTags = null;
    loadLogs(reset: true);
  }

  Future<void> loadMore() => loadLogs(reset: false);
}
