import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import '../../core/app_colors.dart';
import '../../models/medication.dart';
import '../../providers/auth_provider.dart';
import '../../providers/medication_provider.dart';
import '../../providers/patient_provider.dart';
import 'add_medication_screen.dart';
import 'edit_medication_screen.dart';

class MedicationsScreen extends StatefulWidget {
  const MedicationsScreen({super.key});

  @override
  State<MedicationsScreen> createState() => _MedicationsScreenState();
}

class _MedicationsScreenState extends State<MedicationsScreen> {
  final ScrollController _scrollController = ScrollController();

  @override
  void initState() {
    super.initState();
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
      final provider = context.read<MedicationProvider>();
      if (!provider.isLoadingHistory && provider.hasMoreHistory) {
        provider.loadMoreHistory();
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final patientProv = context.watch<PatientProvider>();
    final medProv = context.watch<MedicationProvider>();

    final canEdit = patientProv.canEditMedicationsForActivePatient(auth.userType);
    final activePatientId = patientProv.activePatientId;

    if (activePatientId == null) {
      return Center(
        child: Text(
          'Select a patient to view medications',
          style: TextStyle(color: AppColors.textSecondary),
        ),
      );
    }

    // Group history by scheduledDate descending
    final grouped = _groupByDate(medProv.adherenceHistory);

    return RefreshIndicator(
      color: AppColors.primary,
      onRefresh: () => medProv.loadAll(),
      child: CustomScrollView(
        controller: _scrollController,
        slivers: [
          // Section A: Adherence Rate Banner
          SliverToBoxAdapter(
            child: _AdherenceRateBanner(rate: medProv.adherenceRate),
          ),

          // Section B: Today's Schedule header
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 20, 16, 8),
              child: Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          "Today's Schedule",
                          style: GoogleFonts.lexend(
                            fontSize: 16,
                            fontWeight: FontWeight.w700,
                            color: AppColors.textPrimary,
                          ),
                        ),
                        if (patientProv.activePatientName != null)
                          Text(
                            patientProv.activePatientName!,
                            style: TextStyle(
                              fontSize: 12,
                              color: AppColors.textSecondary,
                            ),
                          ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),

          // Today's schedule chips
          SliverToBoxAdapter(
            child: medProv.isLoading
                ? const Padding(
                    padding: EdgeInsets.all(16),
                    child: Center(
                      child: CircularProgressIndicator(color: AppColors.primary),
                    ),
                  )
                : medProv.todaysSchedule.isEmpty
                    ? Padding(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 16, vertical: 8),
                        child: Text(
                          'No medications scheduled for today.',
                          style: TextStyle(color: AppColors.textSecondary),
                        ),
                      )
                    : SizedBox(
                        height: 90,
                        child: ListView.builder(
                          scrollDirection: Axis.horizontal,
                          padding: const EdgeInsets.symmetric(horizontal: 16),
                          itemCount: medProv.todaysSchedule.length,
                          itemBuilder: (context, index) {
                            final schedule = medProv.todaysSchedule[index];
                            return _ScheduleChip(
                              schedule: schedule,
                              canEdit: canEdit,
                              onTap: () => _showDetailSheet(
                                context,
                                schedule,
                                canEdit,
                                medProv,
                              ),
                            );
                          },
                        ),
                      ),
          ),

          // Section C: Add Medication button (doctor with edit perms only)
          if (canEdit)
            SliverToBoxAdapter(
              child: Padding(
                padding:
                    const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                child: OutlinedButton.icon(
                  onPressed: () => Navigator.of(context).push(
                    MaterialPageRoute(
                      builder: (_) => AddMedicationScreen(
                        patientId: activePatientId,
                      ),
                    ),
                  ),
                  icon: const Icon(Icons.add),
                  label: const Text('Add Medication'),
                  style: OutlinedButton.styleFrom(
                    foregroundColor: AppColors.primary,
                    side: BorderSide(color: AppColors.primary),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                    padding: const EdgeInsets.symmetric(vertical: 14),
                  ),
                ),
              ),
            ),

          // Section D: Adherence History header
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 20, 16, 8),
              child: Row(
                children: [
                  Text(
                    'Adherence History',
                    style: GoogleFonts.lexend(
                      fontSize: 16,
                      fontWeight: FontWeight.w700,
                      color: AppColors.textPrimary,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                    decoration: BoxDecoration(
                      color: AppColors.primaryLighter,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Text(
                      '30 days',
                      style: TextStyle(
                        fontSize: 11,
                        color: AppColors.primary,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),

          // Date grouped history
          if (grouped.isEmpty && !medProv.isLoadingHistory)
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Text(
                  'No history available.',
                  style: TextStyle(color: AppColors.textSecondary),
                ),
              ),
            ),

          for (final entry in grouped.entries) ...[
            SliverToBoxAdapter(
              child: _DateGroupHeader(dateLabel: entry.key),
            ),
            SliverList(
              delegate: SliverChildBuilderDelegate(
                (context, index) {
                  final adherence = entry.value[index];
                  return _AdherenceHistoryCard(
                    adherence: adherence,
                    canEdit: canEdit,
                    onMarkTaken: () async {
                      final ok =
                          await medProv.markTaken(adherence.id);
                      if (ok && context.mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(
                            content: Text('Marked as taken'),
                            backgroundColor: AppColors.success,
                          ),
                        );
                      }
                    },
                    onSkip: () => _showSkipDialog(context, medProv, adherence.id),
                  );
                },
                childCount: entry.value.length,
              ),
            ),
          ],

          // Loading more indicator
          SliverToBoxAdapter(
            child: medProv.isLoadingHistory
                ? const Padding(
                    padding: EdgeInsets.all(16),
                    child: Center(
                      child: CircularProgressIndicator(
                          color: AppColors.primary),
                    ),
                  )
                : const SizedBox(height: 20),
          ),
        ],
      ),
    );
  }

  /// Groups adherence history by scheduledDate label, newest first.
  Map<String, List<MedicationAdherence>> _groupByDate(
      List<MedicationAdherence> history) {
    final sorted = List<MedicationAdherence>.from(history)
      ..sort((a, b) => b.scheduledDate.compareTo(a.scheduledDate));

    final map = <String, List<MedicationAdherence>>{};
    for (final item in sorted) {
      final key = DateFormat('EEEE, MMM d').format(item.scheduledDate);
      map.putIfAbsent(key, () => []).add(item);
    }
    return map;
  }

  void _showDetailSheet(
    BuildContext context,
    MedicationSchedule schedule,
    bool canEdit,
    MedicationProvider medProv,
  ) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => _MedicationDetailSheet(
        schedule: schedule,
        canEdit: canEdit,
        onMarkTaken: () async {
          Navigator.pop(context);
          final ok = await medProv.markTaken(schedule.id);
          if (ok && context.mounted) {
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(
                content: Text('Marked as taken'),
                backgroundColor: AppColors.success,
              ),
            );
          }
        },
        onSkip: () {
          Navigator.pop(context);
          _showSkipDialog(context, medProv, schedule.id);
        },
        onEdit: canEdit
            ? () {
                Navigator.pop(context);
                final med = context
                    .read<MedicationProvider>()
                    .medications
                    .where((m) => m.id == schedule.medication.id)
                    .firstOrNull;
                if (med != null) {
                  Navigator.of(context).push(
                    MaterialPageRoute(
                      builder: (_) => EditMedicationScreen(medication: med),
                    ),
                  );
                }
              }
            : null,
        onDelete: canEdit
            ? () => _showDeleteDialog(
                context, medProv, schedule.medication.id, schedule.medication.medicationName)
            : null,
      ),
    );
  }

  void _showDeleteDialog(
      BuildContext context, MedicationProvider medProv, int medId, String name) {
    Navigator.pop(context); // close bottom sheet first
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        title: const Text('Delete Medication'),
        content: Text(
            'Are you sure you want to delete "$name"? This will remove all associated adherence records.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: AppColors.error,
              foregroundColor: Colors.white,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            ),
            onPressed: () async {
              Navigator.pop(ctx);
              final ok = await medProv.deleteMedication(medId);
              if (context.mounted) {
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content: Text(ok ? '$name deleted' : 'Failed to delete'),
                    backgroundColor: ok ? AppColors.error : AppColors.warning,
                  ),
                );
              }
            },
            child: const Text('Delete'),
          ),
        ],
      ),
    );
  }

  void _showSkipDialog(
      BuildContext context, MedicationProvider medProv, int adherenceId) {
    final reasonController = TextEditingController();
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Skip Medication'),
        content: TextField(
          controller: reasonController,
          decoration: const InputDecoration(
            labelText: 'Reason',
            hintText: 'e.g. Patient refused',
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.primary,
                foregroundColor: Colors.white),
            onPressed: () async {
              Navigator.pop(ctx);
              final reason =
                  reasonController.text.isEmpty ? 'No reason' : reasonController.text;
              final ok = await medProv.skipMedication(adherenceId, reason);
              if (ok && context.mounted) {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text('Medication skipped'),
                    backgroundColor: AppColors.warning,
                  ),
                );
              }
            },
            child: const Text('Skip'),
          ),
        ],
      ),
    );
  }
}

// ============================================================
// Adherence Rate Banner
// ============================================================

class _AdherenceRateBanner extends StatelessWidget {
  final double rate;
  const _AdherenceRateBanner({required this.rate});

  @override
  Widget build(BuildContext context) {
    final pct = (rate * 100).round();
    final Color color;
    final String message;

    if (pct >= 90) {
      color = AppColors.vitalsGreen;
      message = 'Excellent';
    } else if (pct >= 70) {
      color = AppColors.warning;
      message = 'Good';
    } else {
      color = AppColors.error;
      message = 'Needs attention';
    }

    return Container(
      margin: const EdgeInsets.fromLTRB(16, 16, 16, 0),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(20),
        boxShadow: [
          BoxShadow(
            color: AppColors.shadowLight,
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Row(
        children: [
          Container(
            width: 60,
            height: 60,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: color.withOpacity(0.12),
              border: Border.all(color: color, width: 2),
            ),
            alignment: Alignment.center,
            child: Text(
              '$pct%',
              style: GoogleFonts.lexend(
                fontSize: 16,
                fontWeight: FontWeight.w700,
                color: color,
              ),
            ),
          ),
          const SizedBox(width: 16),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '7-day adherence',
                style: TextStyle(
                  fontSize: 12,
                  color: AppColors.textSecondary,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                message,
                style: GoogleFonts.lexend(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                  color: color,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

// ============================================================
// Schedule Chip
// ============================================================

class _ScheduleChip extends StatelessWidget {
  final MedicationSchedule schedule;
  final bool canEdit;
  final VoidCallback onTap;

  const _ScheduleChip({
    required this.schedule,
    required this.canEdit,
    required this.onTap,
  });

  Color _statusColor(String status) {
    switch (status) {
      case 'TAKEN':
        return AppColors.vitalsGreen;
      case 'MISSED':
        return AppColors.error;
      case 'SKIPPED':
        return AppColors.textTertiary;
      default:
        return AppColors.warning;
    }
  }

  @override
  Widget build(BuildContext context) {
    final dotColor = _statusColor(schedule.status);
    final timeStr = DateFormat('HH:mm').format(schedule.scheduledTime);

    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 130,
        margin: const EdgeInsets.only(right: 10),
        padding: const EdgeInsets.all(10),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: AppColors.border),
          boxShadow: [
            BoxShadow(
              color: AppColors.shadowLight,
              blurRadius: 4,
              offset: const Offset(0, 1),
            ),
          ],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.medication,
                    size: 16, color: AppColors.primary),
                const Spacer(),
                Container(
                  width: 8,
                  height: 8,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: dotColor,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 6),
            Text(
              schedule.medication.medicationName,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: GoogleFonts.lexend(
                fontSize: 12,
                fontWeight: FontWeight.w600,
                color: AppColors.textPrimary,
              ),
            ),
            const SizedBox(height: 2),
            Text(
              timeStr,
              style: TextStyle(
                fontSize: 11,
                color: AppColors.textSecondary,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ============================================================
// Date Group Header
// ============================================================

class _DateGroupHeader extends StatelessWidget {
  final String dateLabel;
  const _DateGroupHeader({required this.dateLabel});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
      child: Text(
        dateLabel,
        style: GoogleFonts.lexend(
          fontSize: 13,
          fontWeight: FontWeight.w600,
          color: AppColors.textSecondary,
        ),
      ),
    );
  }
}

// ============================================================
// Adherence History Card
// ============================================================

class _AdherenceHistoryCard extends StatelessWidget {
  final MedicationAdherence adherence;
  final bool canEdit;
  final VoidCallback onMarkTaken;
  final VoidCallback onSkip;

  const _AdherenceHistoryCard({
    required this.adherence,
    required this.canEdit,
    required this.onMarkTaken,
    required this.onSkip,
  });

  IconData _statusIcon(String status) {
    switch (status) {
      case 'TAKEN':
        return Icons.check_circle;
      case 'SKIPPED':
        return Icons.cancel;
      case 'MISSED':
        return Icons.warning_amber_rounded;
      default:
        return Icons.hourglass_empty;
    }
  }

  Color _statusColor(String status) {
    switch (status) {
      case 'TAKEN':
        return AppColors.vitalsGreen;
      case 'MISSED':
        return AppColors.error;
      case 'SKIPPED':
        return AppColors.textTertiary;
      default:
        return AppColors.warning;
    }
  }

  Widget? _confirmationBadge(String method) {
    switch (method) {
      case 'MONITOR_AGENT':
        return _badge('AI', const Color(0xFF0D9488));
      case 'AI_VERBAL':
        return _badge('Voice', const Color(0xFF8B5CF6));
      case 'FAMILY':
        return _badge('Family', AppColors.vitalsBlue);
      default:
        return null;
    }
  }

  Widget _badge(String label, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: color.withOpacity(0.12),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withOpacity(0.4)),
      ),
      child: Text(
        label,
        style: TextStyle(
          fontSize: 10,
          fontWeight: FontWeight.w600,
          color: color,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final statusColor = _statusColor(adherence.status);
    final timeStr = adherence.takenAt != null
        ? DateFormat('HH:mm').format(adherence.takenAt!)
        : '';
    final badge = _confirmationBadge(adherence.confirmationMethod);

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: AppColors.shadowLight,
            blurRadius: 6,
            offset: const Offset(0, 1),
          ),
        ],
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Status icon circle
          Container(
            width: 36,
            height: 36,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: statusColor.withOpacity(0.12),
            ),
            child: Icon(_statusIcon(adherence.status),
                size: 18, color: statusColor),
          ),
          const SizedBox(width: 12),

          // Middle content
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        adherence.medicationName,
                        style: GoogleFonts.lexend(
                          fontSize: 14,
                          fontWeight: FontWeight.w600,
                          color: AppColors.textPrimary,
                        ),
                      ),
                    ),
                    if (badge != null) badge,
                  ],
                ),
                if (adherence.dosage.isNotEmpty)
                  Text(
                    adherence.dosage,
                    style: TextStyle(
                      fontSize: 12,
                      color: AppColors.textSecondary,
                    ),
                  ),
                if (timeStr.isNotEmpty)
                  Text(
                    timeStr,
                    style: TextStyle(
                      fontSize: 11,
                      color: AppColors.textTertiary,
                    ),
                  ),
                if (adherence.notes != null && adherence.notes!.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(top: 4),
                    child: Text(
                      adherence.notes!,
                      style: TextStyle(
                        fontSize: 11,
                        color: AppColors.textSecondary,
                        fontStyle: FontStyle.italic,
                      ),
                    ),
                  ),
              ],
            ),
          ),

          // Mark action for SCHEDULED items (doctor only)
          if (canEdit && adherence.status == 'SCHEDULED') ...[
            const SizedBox(width: 8),
            PopupMenuButton<String>(
              padding: EdgeInsets.zero,
              icon: Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: AppColors.primaryLighter,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  'Mark',
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    color: AppColors.primary,
                  ),
                ),
              ),
              onSelected: (val) {
                if (val == 'taken') onMarkTaken();
                if (val == 'skip') onSkip();
              },
              itemBuilder: (_) => [
                const PopupMenuItem(value: 'taken', child: Text('Taken')),
                const PopupMenuItem(value: 'skip', child: Text('Skip')),
              ],
            ),
          ],
        ],
      ),
    );
  }
}

// ============================================================
// Medication Detail Bottom Sheet
// ============================================================

class _MedicationDetailSheet extends StatelessWidget {
  final MedicationSchedule schedule;
  final bool canEdit;
  final VoidCallback onMarkTaken;
  final VoidCallback onSkip;
  final VoidCallback? onEdit;
  final VoidCallback? onDelete;

  const _MedicationDetailSheet({
    required this.schedule,
    required this.canEdit,
    required this.onMarkTaken,
    required this.onSkip,
    this.onEdit,
    this.onDelete,
  });

  Color _statusColor(String status) {
    switch (status) {
      case 'TAKEN':
        return AppColors.vitalsGreen;
      case 'MISSED':
        return AppColors.error;
      case 'SKIPPED':
        return AppColors.textTertiary;
      default:
        return AppColors.warning;
    }
  }

  @override
  Widget build(BuildContext context) {
    final med = schedule.medication;
    final statusColor = _statusColor(schedule.status);

    return Container(
      decoration: const BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      padding: EdgeInsets.fromLTRB(
          20, 20, 20, MediaQuery.of(context).viewInsets.bottom + 20),
      child: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Handle bar
            Center(
              child: Container(
                width: 40,
                height: 4,
                decoration: BoxDecoration(
                  color: AppColors.divider,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),
            const SizedBox(height: 16),

            Text(
              med.medicationName,
              style: GoogleFonts.lexend(
                fontSize: 22,
                fontWeight: FontWeight.w700,
                color: AppColors.textPrimary,
              ),
            ),
            const SizedBox(height: 12),

            // 2x2 info grid
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                _InfoChip(label: 'Dosage', value: med.dosage),
                _InfoChip(label: 'Form', value: med.form),
                _InfoChip(label: 'Frequency', value: med.frequency),
                _InfoChip(label: 'Route', value: med.route),
              ],
            ),
            const SizedBox(height: 12),

            Row(
              children: [
                Icon(Icons.access_time,
                    size: 16, color: AppColors.textSecondary),
                const SizedBox(width: 6),
                Text(
                  'Scheduled: ${DateFormat('HH:mm').format(schedule.scheduledTime)}',
                  style:
                      TextStyle(fontSize: 13, color: AppColors.textSecondary),
                ),
              ],
            ),
            const SizedBox(height: 8),

            // Status badge
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
              decoration: BoxDecoration(
                color: statusColor.withOpacity(0.1),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: statusColor.withOpacity(0.4)),
              ),
              child: Text(
                schedule.status,
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  color: statusColor,
                ),
              ),
            ),

            if (canEdit && schedule.isScheduled) ...[
              const SizedBox(height: 20),
              Row(
                children: [
                  Expanded(
                    child: ElevatedButton.icon(
                      onPressed: onMarkTaken,
                      icon: const Icon(Icons.check, size: 18),
                      label: const Text('Mark Taken'),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppColors.vitalsGreen,
                        foregroundColor: Colors.white,
                        shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(12)),
                        padding: const EdgeInsets.symmetric(vertical: 14),
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: onSkip,
                      icon: const Icon(Icons.cancel_outlined, size: 18),
                      label: const Text('Skip'),
                      style: OutlinedButton.styleFrom(
                        foregroundColor: AppColors.warning,
                        side: BorderSide(color: AppColors.warning),
                        shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(12)),
                        padding: const EdgeInsets.symmetric(vertical: 14),
                      ),
                    ),
                  ),
                ],
              ),
            ],

            if (onEdit != null) ...[
              const SizedBox(height: 12),
              OutlinedButton.icon(
                onPressed: onEdit,
                icon: const Icon(Icons.edit_outlined, size: 18),
                label: const Text('Edit Medication'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: AppColors.primary,
                  side: BorderSide(color: AppColors.primary),
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12)),
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  minimumSize: const Size.fromHeight(48),
                ),
              ),
            ],
            if (onDelete != null) ...[
              const SizedBox(height: 8),
              OutlinedButton.icon(
                onPressed: onDelete,
                icon: const Icon(Icons.delete_outline, size: 18),
                label: const Text('Delete Medication'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: AppColors.error,
                  side: BorderSide(color: AppColors.error.withOpacity(0.6)),
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12)),
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  minimumSize: const Size.fromHeight(48),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _InfoChip extends StatelessWidget {
  final String label;
  final String value;
  const _InfoChip({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: AppColors.background,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            style: TextStyle(fontSize: 10, color: AppColors.textSecondary),
          ),
          Text(
            value.isEmpty ? '—' : value,
            style: const TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}
