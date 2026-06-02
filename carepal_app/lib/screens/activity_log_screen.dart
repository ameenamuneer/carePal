import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';
import 'package:intl/intl.dart';
import '../core/app_colors.dart';
import '../models/activity_log.dart';
import '../providers/activity_log_provider.dart';

class ActivityLogScreen extends StatefulWidget {
  const ActivityLogScreen({super.key});

  @override
  State<ActivityLogScreen> createState() => _ActivityLogScreenState();
}

class _ActivityLogScreenState extends State<ActivityLogScreen> {
  final ScrollController _scrollController = ScrollController();

  static const _activityTypes = [
    'ALL',
    'MEAL',
    'EXERCISE',
    'SLEEP',
    'SYMPTOM',
    'MEDICATION',
    'MOOD',
    'BEHAVIOR',
    'SOCIAL',
    'ENVIRONMENT',
    'VITAL_OBSERVATION',
    'OTHER',
  ];

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<ActivityLogProvider>().loadLogs();
    });
    _scrollController.addListener(_onScroll);
  }

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  void _onScroll() {
    if (_scrollController.position.pixels >=
        _scrollController.position.maxScrollExtent - 300) {
      context.read<ActivityLogProvider>().loadMore();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: AppColors.background,
        elevation: 0,
        leading: BackButton(color: AppColors.primaryDark),
        title: Text(
          'Activity Log',
          style: GoogleFonts.lexend(
            fontSize: 20,
            fontWeight: FontWeight.bold,
            color: AppColors.primaryDark,
          ),
        ),
        actions: [
          IconButton(
            icon: Icon(Icons.filter_list, color: AppColors.primary),
            onPressed: _showFilterSheet,
          ),
        ],
      ),
      body: Consumer<ActivityLogProvider>(
        builder: (context, provider, _) {
          if (provider.isLoading && provider.logs.isEmpty) {
            return const Center(
              child: CircularProgressIndicator(color: AppColors.primary),
            );
          }

          if (provider.error != null && provider.logs.isEmpty) {
            return Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.error_outline, size: 48, color: AppColors.error),
                  const SizedBox(height: 12),
                  Text(
                    'Failed to load activity logs',
                    style: TextStyle(color: AppColors.textSecondary),
                  ),
                  const SizedBox(height: 16),
                  ElevatedButton(
                    onPressed: () => provider.loadLogs(),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppColors.primary,
                    ),
                    child: const Text('Retry',
                        style: TextStyle(color: Colors.white)),
                  ),
                ],
              ),
            );
          }

          if (provider.logs.isEmpty) {
            return Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.history, size: 64, color: AppColors.primaryLight),
                  const SizedBox(height: 16),
                  Text(
                    'No activity logs yet',
                    style: GoogleFonts.lexend(
                      fontSize: 18,
                      color: AppColors.textPrimary,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'Logs are captured automatically\nduring AI conversations.',
                    textAlign: TextAlign.center,
                    style: TextStyle(color: AppColors.textSecondary),
                  ),
                ],
              ),
            );
          }

          return Column(
            children: [
              _buildActiveFiltersBar(provider),
              _buildCountBar(provider),
              Expanded(
                child: RefreshIndicator(
                  color: AppColors.primary,
                  onRefresh: () => provider.loadLogs(),
                  child: ListView.builder(
                    controller: _scrollController,
                    padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
                    itemCount:
                        provider.logs.length + (provider.hasMore ? 1 : 0),
                    itemBuilder: (context, index) {
                      if (index == provider.logs.length) {
                        return const Padding(
                          padding: EdgeInsets.symmetric(vertical: 16),
                          child: Center(
                            child: CircularProgressIndicator(
                                color: AppColors.primary),
                          ),
                        );
                      }
                      return _ActivityLogCard(log: provider.logs[index]);
                    },
                  ),
                ),
              ),
            ],
          );
        },
      ),
    );
  }

  Widget _buildCountBar(ActivityLogProvider provider) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 4, 16, 4),
      child: Row(
        children: [
          Text(
            '${provider.totalCount} entries',
            style: TextStyle(
              fontSize: 13,
              color: AppColors.textSecondary,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildActiveFiltersBar(ActivityLogProvider provider) {
    final hasFilters =
        provider.filterType != null || provider.filterNotable != null;
    if (!hasFilters) return const SizedBox.shrink();

    return Container(
      height: 40,
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Row(
        children: [
          if (provider.filterType != null)
            _FilterChip(
              label: provider.filterType!,
              color: _typeColor(provider.filterType!),
              onRemove: () => provider.setFilters(isNotable: provider.filterNotable),
            ),
          if (provider.filterNotable == true)
            _FilterChip(
              label: 'Notable',
              color: AppColors.alert,
              onRemove: () => provider.setFilters(activityType: provider.filterType),
            ),
          const Spacer(),
          TextButton(
            onPressed: provider.clearFilters,
            child: Text('Clear all',
                style: TextStyle(color: AppColors.primary, fontSize: 12)),
          ),
        ],
      ),
    );
  }

  void _showFilterSheet() {
    final provider = context.read<ActivityLogProvider>();
    String? selectedType = provider.filterType;
    bool notableOnly = provider.filterNotable ?? false;

    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      isScrollControlled: true,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setModalState) => Container(
          padding: const EdgeInsets.all(24),
          decoration: const BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Filter Logs',
                style: GoogleFonts.lexend(
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                  color: AppColors.primaryDark,
                ),
              ),
              const SizedBox(height: 20),
              Text('Activity Type',
                  style: TextStyle(
                      fontWeight: FontWeight.w600,
                      color: AppColors.textPrimary)),
              const SizedBox(height: 10),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: _activityTypes.map((type) {
                  final isAll = type == 'ALL';
                  final isSelected = isAll
                      ? selectedType == null
                      : selectedType == type;
                  return ChoiceChip(
                    label: Text(
                      isAll ? 'All' : _typeLabel(type),
                      style: TextStyle(
                        fontSize: 12,
                        color: isSelected ? Colors.white : AppColors.textPrimary,
                      ),
                    ),
                    selected: isSelected,
                    selectedColor: isAll
                        ? AppColors.primary
                        : _typeColor(type),
                    backgroundColor: AppColors.background,
                    onSelected: (_) => setModalState(() {
                      selectedType = isAll ? null : type;
                    }),
                  );
                }).toList(),
              ),
              const SizedBox(height: 20),
              SwitchListTile(
                contentPadding: EdgeInsets.zero,
                title: const Text('Notable events only'),
                value: notableOnly,
                activeColor: AppColors.alert,
                onChanged: (v) => setModalState(() => notableOnly = v),
              ),
              const SizedBox(height: 16),
              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: () {
                    Navigator.pop(ctx);
                    provider.setFilters(
                      activityType: selectedType,
                      isNotable: notableOnly ? true : null,
                    );
                  },
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppColors.primary,
                    padding: const EdgeInsets.symmetric(vertical: 14),
                    shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(14)),
                  ),
                  child: const Text('Apply Filters',
                      style: TextStyle(color: Colors.white, fontSize: 15)),
                ),
              ),
              SizedBox(height: MediaQuery.of(ctx).viewInsets.bottom + 8),
            ],
          ),
        ),
      ),
    );
  }
}

class _FilterChip extends StatelessWidget {
  final String label;
  final Color color;
  final VoidCallback onRemove;

  const _FilterChip({
    required this.label,
    required this.color,
    required this.onRemove,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(right: 8),
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: color.withOpacity(0.15),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: color.withOpacity(0.4)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(label,
              style: TextStyle(
                  fontSize: 12,
                  color: color,
                  fontWeight: FontWeight.w600)),
          const SizedBox(width: 4),
          GestureDetector(
            onTap: onRemove,
            child: Icon(Icons.close, size: 14, color: color),
          ),
        ],
      ),
    );
  }
}

class _ActivityLogCard extends StatelessWidget {
  final ActivityLog log;

  const _ActivityLogCard({required this.log});

  @override
  Widget build(BuildContext context) {
    final color = _typeColor(log.activityType);
    final icon = _typeIcon(log.activityType);
    final dateStr = DateFormat('MMM d, yyyy • h:mm a').format(
      log.observedAt.toLocal(),
    );

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(
          color: log.isNotable
              ? AppColors.alert.withOpacity(0.4)
              : color.withOpacity(0.12),
          width: log.isNotable ? 1.5 : 1,
        ),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.03),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: color.withOpacity(0.12),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Icon(icon, color: color, size: 18),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        _typeLabel(log.activityType),
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                          color: color,
                          letterSpacing: 0.5,
                        ),
                      ),
                      Text(
                        dateStr,
                        style: TextStyle(
                          fontSize: 11,
                          color: AppColors.textTertiary,
                        ),
                      ),
                    ],
                  ),
                ),
                if (log.isNotable)
                  Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                    decoration: BoxDecoration(
                      color: AppColors.alert.withOpacity(0.12),
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.warning_amber_rounded,
                            size: 12, color: AppColors.alert),
                        const SizedBox(width: 3),
                        Text(
                          'Notable',
                          style: TextStyle(
                            fontSize: 10,
                            fontWeight: FontWeight.w700,
                            color: AppColors.alert,
                          ),
                        ),
                      ],
                    ),
                  ),
                const SizedBox(width: 6),
                _ConfidenceDot(confidence: log.aiConfidence),
              ],
            ),
            const SizedBox(height: 12),
            Text(
              log.description,
              style: TextStyle(
                fontSize: 14,
                color: AppColors.textPrimary,
                height: 1.4,
              ),
            ),
            if (log.isNotable && log.notableReason != null) ...[
              const SizedBox(height: 8),
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: AppColors.alert.withOpacity(0.06),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(Icons.info_outline,
                        size: 14, color: AppColors.alert),
                    const SizedBox(width: 6),
                    Expanded(
                      child: Text(
                        log.notableReason!,
                        style: TextStyle(
                          fontSize: 12,
                          color: AppColors.alert,
                          height: 1.4,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ],
            if (log.tags.isNotEmpty) ...[
              const SizedBox(height: 10),
              Wrap(
                spacing: 6,
                runSpacing: 4,
                children: log.tags
                    .map((tag) => Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 8, vertical: 2),
                          decoration: BoxDecoration(
                            color: AppColors.primaryLighter,
                            borderRadius: BorderRadius.circular(20),
                          ),
                          child: Text(
                            '#$tag',
                            style: TextStyle(
                              fontSize: 11,
                              color: AppColors.primary,
                            ),
                          ),
                        ))
                    .toList(),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _ConfidenceDot extends StatelessWidget {
  final String confidence;
  const _ConfidenceDot({required this.confidence});

  @override
  Widget build(BuildContext context) {
    final color = confidence == 'HIGH'
        ? AppColors.vitalsGreen
        : confidence == 'MEDIUM'
            ? AppColors.vitalsOrange
            : AppColors.textTertiary;
    return Tooltip(
      message: '$confidence confidence',
      child: Container(
        width: 8,
        height: 8,
        decoration: BoxDecoration(color: color, shape: BoxShape.circle),
      ),
    );
  }
}

Color _typeColor(String type) {
  switch (type) {
    case 'MEAL':
      return const Color(0xFF10B981);
    case 'EXERCISE':
      return const Color(0xFF3B82F6);
    case 'SLEEP':
      return const Color(0xFF8B5CF6);
    case 'SYMPTOM':
      return const Color(0xFFEF4444);
    case 'MEDICATION':
      return const Color(0xFF0D9488);
    case 'MOOD':
      return const Color(0xFFF59E0B);
    case 'BEHAVIOR':
      return const Color(0xFF6366F1);
    case 'SOCIAL':
      return const Color(0xFFEC4899);
    case 'ENVIRONMENT':
      return const Color(0xFF64748B);
    case 'VITAL_OBSERVATION':
      return const Color(0xFFF97316);
    default:
      return const Color(0xFF94A3B8);
  }
}

IconData _typeIcon(String type) {
  switch (type) {
    case 'MEAL':
      return Icons.restaurant;
    case 'EXERCISE':
      return Icons.directions_walk;
    case 'SLEEP':
      return Icons.bedtime;
    case 'SYMPTOM':
      return Icons.sick;
    case 'MEDICATION':
      return Icons.medication;
    case 'MOOD':
      return Icons.mood;
    case 'BEHAVIOR':
      return Icons.psychology;
    case 'SOCIAL':
      return Icons.people;
    case 'ENVIRONMENT':
      return Icons.home;
    case 'VITAL_OBSERVATION':
      return Icons.monitor_heart;
    default:
      return Icons.notes;
  }
}

String _typeLabel(String type) {
  switch (type) {
    case 'MEAL':
      return 'Meal';
    case 'EXERCISE':
      return 'Exercise';
    case 'SLEEP':
      return 'Sleep';
    case 'SYMPTOM':
      return 'Symptom';
    case 'MEDICATION':
      return 'Medication';
    case 'MOOD':
      return 'Mood';
    case 'BEHAVIOR':
      return 'Behavior';
    case 'SOCIAL':
      return 'Social';
    case 'ENVIRONMENT':
      return 'Environment';
    case 'VITAL_OBSERVATION':
      return 'Vital Obs.';
    case 'OTHER':
      return 'Other';
    default:
      return type;
  }
}
