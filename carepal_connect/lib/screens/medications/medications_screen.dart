import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import 'package:table_calendar/table_calendar.dart';
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
  DateTime _focusedDay = DateTime.now();
  DateTime? _selectedDay;

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

    return RefreshIndicator(
      color: AppColors.primary,
      onRefresh: () => medProv.loadAll(),
      child: CustomScrollView(
        slivers: [
          // Adherence Rate Banner
          SliverToBoxAdapter(
            child: _AdherenceRateBanner(rate: medProv.adherenceRate),
          ),

          // Today's Schedule header
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 20, 16, 8),
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

          // Add Medication button (doctor with edit perms only)
          if (canEdit)
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
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

          // Adherence Calendar header
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 20, 16, 4),
              child: Row(
                children: [
                  Text(
                    'Adherence Calendar',
                    style: GoogleFonts.lexend(
                      fontSize: 16,
                      fontWeight: FontWeight.w700,
                      color: AppColors.textPrimary,
                    ),
                  ),
                  const SizedBox(width: 8),
                  if (medProv.isLoadingCalendar)
                    const SizedBox(
                      width: 14,
                      height: 14,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: AppColors.primary,
                      ),
                    ),
                  const Spacer(),
                  // Legend
                  _LegendDot(color: AppColors.vitalsGreen, label: 'Good'),
                  const SizedBox(width: 8),
                  _LegendDot(color: AppColors.warning, label: 'Partial'),
                  const SizedBox(width: 8),
                  _LegendDot(color: AppColors.error, label: 'Missed'),
                ],
              ),
            ),
          ),

          // Calendar widget
          SliverToBoxAdapter(
            child: _AdherenceCalendar(
              calendarData: medProv.calendarData,
              focusedDay: _focusedDay,
              selectedDay: _selectedDay,
              onDaySelected: (selected, focused) {
                setState(() {
                  _selectedDay = selected;
                  _focusedDay = focused;
                });
                _showDaySheet(context, selected, medProv, canEdit);
              },
              onPageChanged: (focused) {
                setState(() => _focusedDay = focused);
              },
            ),
          ),

          const SliverToBoxAdapter(child: SizedBox(height: 24)),
        ],
      ),
    );
  }

  void _showDaySheet(
    BuildContext context,
    DateTime day,
    MedicationProvider medProv,
    bool canEdit,
  ) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => _DayScheduleSheet(
        day: day,
        medProv: medProv,
        canEdit: canEdit,
        onMarkTaken: (id) async {
          Navigator.pop(context);
          final ok = await medProv.markTaken(id);
          if (ok && context.mounted) {
            ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
              content: Text('Marked as taken'),
              backgroundColor: AppColors.success,
            ));
          }
        },
        onSkip: (id) {
          Navigator.pop(context);
          _showSkipDialog(context, medProv, id);
        },
      ),
    );
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
            ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
              content: Text('Marked as taken'),
              backgroundColor: AppColors.success,
            ));
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
                  Navigator.of(context).push(MaterialPageRoute(
                    builder: (_) => EditMedicationScreen(medication: med),
                  ));
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
    Navigator.pop(context);
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
                ScaffoldMessenger.of(context).showSnackBar(SnackBar(
                  content: Text(ok ? '$name deleted' : 'Failed to delete'),
                  backgroundColor: ok ? AppColors.error : AppColors.warning,
                ));
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
                backgroundColor: AppColors.primary, foregroundColor: Colors.white),
            onPressed: () async {
              Navigator.pop(ctx);
              final reason =
                  reasonController.text.isEmpty ? 'No reason' : reasonController.text;
              final ok = await medProv.skipMedication(adherenceId, reason);
              if (ok && context.mounted) {
                ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
                  content: Text('Medication skipped'),
                  backgroundColor: AppColors.warning,
                ));
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
// Adherence Calendar
// ============================================================

class _AdherenceCalendar extends StatelessWidget {
  final Map<String, Map<String, int>> calendarData;
  final DateTime focusedDay;
  final DateTime? selectedDay;
  final void Function(DateTime selected, DateTime focused) onDaySelected;
  final void Function(DateTime focused) onPageChanged;

  const _AdherenceCalendar({
    required this.calendarData,
    required this.focusedDay,
    required this.selectedDay,
    required this.onDaySelected,
    required this.onPageChanged,
  });

  Color? _colorForDay(DateTime day) {
    final today = DateTime.now();
    final isToday = isSameDay(day, today);
    final isFuture = day.isAfter(today) && !isToday;

    if (isFuture) return const Color(0xFF3B82F6); // blue for future

    final key =
        '${day.year}-${day.month.toString().padLeft(2, '0')}-${day.day.toString().padLeft(2, '0')}';
    final data = calendarData[key];
    if (data == null) return null; // no data — no dot

    final total = data['total'] ?? 0;
    final taken = data['taken'] ?? 0;
    if (total == 0) return null;

    final rate = taken / total;
    if (rate >= 0.8) return AppColors.vitalsGreen;
    if (rate >= 0.4) return AppColors.warning;
    return AppColors.error;
  }

  bool _hasDot(DateTime day) {
    final today = DateTime.now();
    final isToday = isSameDay(day, today);
    final isFuture = day.isAfter(today) && !isToday;
    if (isFuture) return true;
    final key =
        '${day.year}-${day.month.toString().padLeft(2, '0')}-${day.day.toString().padLeft(2, '0')}';
    return calendarData.containsKey(key);
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16),
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
      child: TableCalendar(
        firstDay: DateTime.now().subtract(const Duration(days: 90)),
        lastDay: DateTime.now().add(const Duration(days: 60)),
        focusedDay: focusedDay,
        selectedDayPredicate: (d) => isSameDay(d, selectedDay),
        onDaySelected: onDaySelected,
        onPageChanged: onPageChanged,
        calendarFormat: CalendarFormat.month,
        availableCalendarFormats: const {CalendarFormat.month: 'Month'},
        headerStyle: HeaderStyle(
          formatButtonVisible: false,
          titleCentered: true,
          titleTextStyle: GoogleFonts.lexend(
            fontSize: 15,
            fontWeight: FontWeight.w600,
            color: AppColors.textPrimary,
          ),
          leftChevronIcon:
              Icon(Icons.chevron_left, color: AppColors.textSecondary),
          rightChevronIcon:
              Icon(Icons.chevron_right, color: AppColors.textSecondary),
          headerPadding: const EdgeInsets.symmetric(vertical: 8),
        ),
        daysOfWeekStyle: DaysOfWeekStyle(
          weekdayStyle: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w600,
              color: AppColors.textSecondary),
          weekendStyle: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w600,
              color: AppColors.textTertiary),
        ),
        calendarStyle: CalendarStyle(
          outsideDaysVisible: false,
          todayDecoration: BoxDecoration(
            color: AppColors.primary.withOpacity(0.15),
            shape: BoxShape.circle,
          ),
          todayTextStyle: TextStyle(
            color: AppColors.primary,
            fontWeight: FontWeight.w700,
          ),
          selectedDecoration: BoxDecoration(
            color: AppColors.primary,
            shape: BoxShape.circle,
          ),
          selectedTextStyle: const TextStyle(
            color: Colors.white,
            fontWeight: FontWeight.w700,
          ),
          defaultTextStyle: TextStyle(color: AppColors.textPrimary),
          weekendTextStyle: TextStyle(color: AppColors.textPrimary),
        ),
        calendarBuilders: CalendarBuilders(
          markerBuilder: (context, day, events) {
            if (!_hasDot(day)) return const SizedBox.shrink();
            final color = _colorForDay(day);
            if (color == null) return const SizedBox.shrink();
            return Positioned(
              bottom: 4,
              child: Container(
                width: 6,
                height: 6,
                decoration: BoxDecoration(
                  color: color,
                  shape: BoxShape.circle,
                ),
              ),
            );
          },
          // Tint the entire day cell background for past days
          defaultBuilder: (context, day, focusedDay) {
            final color = _colorForDay(day);
            if (color == null) return null;
            final today = DateTime.now();
            final isFuture = day.isAfter(today) && !isSameDay(day, today);
            if (isFuture) return null; // future — only dot, no bg tint
            return Container(
              margin: const EdgeInsets.all(4),
              decoration: BoxDecoration(
                color: color.withOpacity(0.12),
                shape: BoxShape.circle,
              ),
              alignment: Alignment.center,
              child: Text(
                '${day.day}',
                style: TextStyle(
                  fontSize: 13,
                  color: color.withOpacity(0.9),
                  fontWeight: FontWeight.w600,
                ),
              ),
            );
          },
        ),
      ),
    );
  }
}

// ============================================================
// Day Schedule Bottom Sheet
// ============================================================

class _DayScheduleSheet extends StatefulWidget {
  final DateTime day;
  final MedicationProvider medProv;
  final bool canEdit;
  final void Function(int id) onMarkTaken;
  final void Function(int id) onSkip;

  const _DayScheduleSheet({
    required this.day,
    required this.medProv,
    required this.canEdit,
    required this.onMarkTaken,
    required this.onSkip,
  });

  @override
  State<_DayScheduleSheet> createState() => _DayScheduleSheetState();
}

class _DayScheduleSheetState extends State<_DayScheduleSheet> {
  List<MedicationSchedule>? _schedule;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    widget.medProv.loadDaySchedule(widget.day).then((list) {
      if (mounted) setState(() { _schedule = list; _loading = false; });
    });
  }

  @override
  Widget build(BuildContext context) {
    final dateLabel = DateFormat('EEEE, MMMM d, yyyy').format(widget.day);
    final today = DateTime.now();
    final isFuture = widget.day.isAfter(DateTime(today.year, today.month, today.day));

    return Container(
      constraints: BoxConstraints(
        maxHeight: MediaQuery.of(context).size.height * 0.65,
      ),
      decoration: const BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      padding: EdgeInsets.fromLTRB(
          20, 16, 20, MediaQuery.of(context).viewInsets.bottom + 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          // Handle
          Center(
            child: Container(
              width: 40, height: 4,
              decoration: BoxDecoration(
                color: AppColors.divider,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
          ),
          const SizedBox(height: 14),
          Text(
            dateLabel,
            style: GoogleFonts.lexend(
              fontSize: 16,
              fontWeight: FontWeight.w700,
              color: AppColors.textPrimary,
            ),
          ),
          const SizedBox(height: 12),
          if (_loading)
            const Padding(
              padding: EdgeInsets.all(24),
              child: Center(child: CircularProgressIndicator(color: AppColors.primary)),
            )
          else if (_schedule == null || _schedule!.isEmpty)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 24),
              child: Center(
                child: Text(
                  'No medications scheduled for this day.',
                  style: TextStyle(color: AppColors.textSecondary),
                ),
              ),
            )
          else
            Flexible(
              child: ListView.builder(
                shrinkWrap: true,
                itemCount: _schedule!.length,
                itemBuilder: (ctx, i) {
                  final s = _schedule![i];
                  return _DayScheduleRow(
                    schedule: s,
                    canEdit: widget.canEdit && !isFuture,
                    onMarkTaken: () => widget.onMarkTaken(s.id),
                    onSkip: () => widget.onSkip(s.id),
                  );
                },
              ),
            ),
        ],
      ),
    );
  }
}

class _DayScheduleRow extends StatelessWidget {
  final MedicationSchedule schedule;
  final bool canEdit;
  final VoidCallback onMarkTaken;
  final VoidCallback onSkip;

  const _DayScheduleRow({
    required this.schedule,
    required this.canEdit,
    required this.onMarkTaken,
    required this.onSkip,
  });

  Color _statusColor(String s) {
    switch (s) {
      case 'TAKEN': return AppColors.vitalsGreen;
      case 'MISSED': return AppColors.error;
      case 'SKIPPED': return AppColors.textTertiary;
      default: return AppColors.warning;
    }
  }

  IconData _statusIcon(String s) {
    switch (s) {
      case 'TAKEN': return Icons.check_circle;
      case 'MISSED': return Icons.warning_amber_rounded;
      case 'SKIPPED': return Icons.cancel;
      default: return Icons.schedule;
    }
  }

  @override
  Widget build(BuildContext context) {
    final color = _statusColor(schedule.status);
    final timeStr = DateFormat('HH:mm').format(schedule.scheduledTime);

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.background,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: color.withOpacity(0.3)),
      ),
      child: Row(
        children: [
          Icon(_statusIcon(schedule.status), size: 20, color: color),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  schedule.medication.medicationName,
                  style: GoogleFonts.lexend(
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                    color: AppColors.textPrimary,
                  ),
                ),
                Text(
                  '$timeStr · ${schedule.medication.dosage}',
                  style: TextStyle(fontSize: 11, color: AppColors.textSecondary),
                ),
              ],
            ),
          ),
          if (canEdit && schedule.isScheduled)
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
      ),
    );
  }
}

// ============================================================
// Legend dot
// ============================================================

class _LegendDot extends StatelessWidget {
  final Color color;
  final String label;
  const _LegendDot({required this.color, required this.label});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 8, height: 8,
          decoration: BoxDecoration(color: color, shape: BoxShape.circle),
        ),
        const SizedBox(width: 4),
        Text(label, style: TextStyle(fontSize: 10, color: AppColors.textSecondary)),
      ],
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
                style: TextStyle(fontSize: 12, color: AppColors.textSecondary),
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
// Schedule Chip (today's horizontal list)
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
      case 'TAKEN': return AppColors.vitalsGreen;
      case 'MISSED': return AppColors.error;
      case 'SKIPPED': return AppColors.textTertiary;
      default: return AppColors.warning;
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
                Icon(Icons.medication, size: 16, color: AppColors.primary),
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
              style: TextStyle(fontSize: 11, color: AppColors.textSecondary),
            ),
          ],
        ),
      ),
    );
  }
}

// ============================================================
// Medication Detail Bottom Sheet (for today's chips)
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
      case 'TAKEN': return AppColors.vitalsGreen;
      case 'MISSED': return AppColors.error;
      case 'SKIPPED': return AppColors.textTertiary;
      default: return AppColors.warning;
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
            Center(
              child: Container(
                width: 40, height: 4,
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
                Icon(Icons.access_time, size: 16, color: AppColors.textSecondary),
                const SizedBox(width: 6),
                Text(
                  'Scheduled: ${DateFormat('HH:mm').format(schedule.scheduledTime)}',
                  style: TextStyle(fontSize: 13, color: AppColors.textSecondary),
                ),
              ],
            ),
            const SizedBox(height: 8),
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
          Text(label,
              style: TextStyle(fontSize: 10, color: AppColors.textSecondary)),
          Text(
            value.isEmpty ? '—' : value,
            style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
          ),
        ],
      ),
    );
  }
}
