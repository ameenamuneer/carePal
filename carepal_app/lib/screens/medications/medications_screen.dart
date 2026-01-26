import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:font_awesome_flutter/font_awesome_flutter.dart';
import '../../core/app_colors.dart';
import '../../providers/medication_provider.dart';
import '../../widgets/loading_shimmer.dart';
import '../../widgets/error_view.dart';
import '../../widgets/empty_state.dart';
import 'medication_detail_screen.dart';
import 'add_medication_screen.dart';

class MedicationsScreen extends StatefulWidget {
  const MedicationsScreen({super.key});

  @override
  State<MedicationsScreen> createState() => _MedicationsScreenState();
}

class _MedicationsScreenState extends State<MedicationsScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    _loadData();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _loadData() async {
    final provider = context.read<MedicationProvider>();
    await Future.wait([
      provider.loadTodaysSchedule(),
      provider.loadMedications(),
      provider.loadAdherenceRate(days: 7),
    ]);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      floatingActionButton: FloatingActionButton(
        onPressed: () {
          Navigator.push(
            context,
            MaterialPageRoute(builder: (_) => const AddMedicationScreen()),
          );
        },
        backgroundColor: AppColors.primary,
        child: const Icon(Icons.add, color: Colors.white),
      ),
      appBar: AppBar(
        backgroundColor: AppColors.surface,
        elevation: 0,
        leading: IconButton(
          icon: Icon(Icons.arrow_back, color: AppColors.textPrimary),
          onPressed: () => Navigator.pop(context),
        ),
        title: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: AppColors.primary.withOpacity(0.1),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Icon(
                FontAwesomeIcons.pills,
                color: AppColors.primary,
                size: 20,
              ),
            ),
            const SizedBox(width: 12),
            const Text(
              'Medications',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),
          ],
        ),
        bottom: TabBar(
          controller: _tabController,
          labelColor: AppColors.primary,
          unselectedLabelColor: AppColors.textSecondary,
          indicatorColor: AppColors.primary,
          indicatorWeight: 3,
          tabs: const [
            Tab(text: 'Today'),
            Tab(text: 'All'),
            Tab(text: 'History'),
          ],
        ),
      ),
      body: Consumer<MedicationProvider>(
        builder: (context, provider, _) {
          if (provider.isLoading && provider.medications.isEmpty) {
            return _buildLoadingState();
          }

          if (provider.error != null && provider.medications.isEmpty) {
            return ErrorView(message: provider.error!, onRetry: _loadData);
          }

          return TabBarView(
            controller: _tabController,
            children: [
              _buildTodayTab(provider),
              _buildAllMedicationsTab(provider),
              _buildHistoryTab(provider),
            ],
          );
        },
      ),
    );
  }

  Widget _buildLoadingState() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        children: List.generate(
          5,
          (_) => Padding(
            padding: const EdgeInsets.only(bottom: 16),
            child: LoadingShimmer(height: 100, borderRadius: 20),
          ),
        ),
      ),
    );
  }

  Widget _buildTodayTab(MedicationProvider provider) {
    final schedule = provider.todaysSchedule;

    if (schedule.isEmpty) {
      return const EmptyState(
        icon: Icons.medication_outlined,
        title: 'No medications today',
        message: 'You have no medications scheduled for today.',
      );
    }

    final scheduled = schedule.where((s) => s.isScheduled).toList();
    final taken = schedule.where((s) => s.isTaken).toList();
    final missed = schedule.where((s) => s.isMissed).toList();

    return RefreshIndicator(
      onRefresh: _loadData,
      color: AppColors.primary,
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Adherence Card
            _buildAdherenceCard(provider.adherenceRate),
            const SizedBox(height: 24),

            // Scheduled Section
            if (scheduled.isNotEmpty) ...[
              _buildSectionHeader('Scheduled', scheduled.length),
              const SizedBox(height: 16),
              ...scheduled.map(
                (med) => Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: _buildMedicationCard(med, provider),
                ),
              ),
              const SizedBox(height: 24),
            ],

            // Taken Section
            if (taken.isNotEmpty) ...[
              _buildSectionHeader('Completed', taken.length),
              const SizedBox(height: 16),
              ...taken.map(
                (med) => Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: _buildMedicationCard(med, provider),
                ),
              ),
              const SizedBox(height: 24),
            ],

            // Missed Section
            if (missed.isNotEmpty) ...[
              _buildSectionHeader('Missed', missed.length),
              const SizedBox(height: 16),
              ...missed.map(
                (med) => Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: _buildMedicationCard(med, provider),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildAllMedicationsTab(MedicationProvider provider) {
    final medications = provider.medications;

    if (medications.isEmpty) {
      return const EmptyState(
        icon: Icons.medication_outlined,
        title: 'No medications',
        message: 'You have no medications in your profile.',
      );
    }

    return RefreshIndicator(
      onRefresh: _loadData,
      color: AppColors.primary,
      child: ListView.separated(
        padding: const EdgeInsets.all(20),
        itemCount: medications.length,
        separatorBuilder: (_, __) => const SizedBox(height: 12),
        itemBuilder: (context, index) {
          final med = medications[index];
          return _buildMedicationListItem(med);
        },
      ),
    );
  }

  Widget _buildHistoryTab(MedicationProvider provider) {
    return const Center(
      child: EmptyState(
        icon: Icons.history,
        title: 'History Coming Soon',
        message: 'Detailed medication history will be available here.',
      ),
    );
  }

  Widget _buildAdherenceCard(double adherenceRate) {
    final percentage = adherenceRate.toInt();
    final color = percentage >= 80
        ? AppColors.success
        : percentage >= 60
        ? AppColors.warning
        : AppColors.error;

    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [color, color.withOpacity(0.8)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(24),
        boxShadow: [
          BoxShadow(
            color: color.withOpacity(0.3),
            blurRadius: 20,
            offset: const Offset(0, 10),
          ),
        ],
      ),
      child: Row(
        children: [
          Container(
            width: 80,
            height: 80,
            decoration: BoxDecoration(
              color: Colors.white.withOpacity(0.2),
              shape: BoxShape.circle,
            ),
            child: Center(
              child: Text(
                '$percentage%',
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 24,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
          ),
          const SizedBox(width: 20),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Adherence Rate',
                  style: TextStyle(
                    color: Colors.white.withOpacity(0.9),
                    fontSize: 14,
                    fontWeight: FontWeight.w500,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  _getAdherenceMessage(percentage),
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  'Last 7 days',
                  style: TextStyle(
                    color: Colors.white.withOpacity(0.8),
                    fontSize: 13,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  String _getAdherenceMessage(int percentage) {
    if (percentage >= 90) return 'Excellent!';
    if (percentage >= 80) return 'Great job!';
    if (percentage >= 70) return 'Good';
    if (percentage >= 60) return 'Needs improvement';
    return 'Critical';
  }

  Widget _buildSectionHeader(String title, int count) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(
          title,
          style: TextStyle(
            fontSize: 18,
            fontWeight: FontWeight.bold,
            color: AppColors.textPrimary,
          ),
        ),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
          decoration: BoxDecoration(
            color: AppColors.primaryLighter,
            borderRadius: BorderRadius.circular(12),
          ),
          child: Text(
            '$count',
            style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.bold,
              color: AppColors.primary,
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildMedicationCard(dynamic schedule, MedicationProvider provider) {
    final med = schedule.medication;
    final isTaken = schedule.isTaken;
    final isScheduled = schedule.isScheduled;
    final isMissed = schedule.isMissed;

    Color statusColor;
    IconData statusIcon;
    String statusText;

    if (isTaken) {
      statusColor = AppColors.success;
      statusIcon = Icons.check_circle;
      statusText = 'Taken';
    } else if (isMissed) {
      statusColor = AppColors.error;
      statusIcon = Icons.cancel;
      statusText = 'Missed';
    } else {
      statusColor = AppColors.alert;
      statusIcon = Icons.schedule;
      statusText = 'Scheduled';
    }

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: statusColor.withOpacity(0.2), width: 1.5),
        boxShadow: [
          BoxShadow(
            color: AppColors.shadowLight,
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 56,
                height: 56,
                decoration: BoxDecoration(
                  color: statusColor.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(16),
                ),
                child: Icon(statusIcon, color: statusColor, size: 28),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      med.medicationName,
                      style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.bold,
                        color: AppColors.textPrimary,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      '${med.dosage} • ${_formatTime(schedule.scheduledTime)}',
                      style: TextStyle(
                        fontSize: 14,
                        color: AppColors.textSecondary,
                      ),
                    ),
                  ],
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 12,
                  vertical: 6,
                ),
                decoration: BoxDecoration(
                  color: statusColor.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(
                  statusText,
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    color: statusColor,
                  ),
                ),
              ),
            ],
          ),
          if (isScheduled) ...[
            const SizedBox(height: 16),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: () =>
                        _handleMarkTaken(schedule.medication.id, provider),
                    icon: Icon(Icons.check, size: 18),
                    label: const Text('Mark Taken'),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: AppColors.success,
                      side: BorderSide(color: AppColors.success, width: 1.5),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                      padding: const EdgeInsets.symmetric(vertical: 12),
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: () =>
                        _handleSkip(schedule.medication.id, provider),
                    icon: Icon(Icons.close, size: 18),
                    label: const Text('Skip'),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: AppColors.error,
                      side: BorderSide(color: AppColors.error, width: 1.5),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                      padding: const EdgeInsets.symmetric(vertical: 12),
                    ),
                  ),
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildMedicationListItem(dynamic medication) {
    final isActive = medication.status == 'ACTIVE';

    return GestureDetector(
      onTap: () {
        Navigator.push(
          context,
          MaterialPageRoute(
            builder: (_) => MedicationDetailScreen(medication: medication),
          ),
        );
      },
      child: Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(
            color: isActive
                ? AppColors.primary.withOpacity(0.2)
                : AppColors.border,
            width: 1,
          ),
        ),
        child: Row(
          children: [
            Container(
              width: 56,
              height: 56,
              decoration: BoxDecoration(
                color: AppColors.primary.withOpacity(0.1),
                borderRadius: BorderRadius.circular(16),
              ),
              child: Icon(
                FontAwesomeIcons.pills,
                color: AppColors.primary,
                size: 24,
              ),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    medication.medicationName,
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                      color: AppColors.textPrimary,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    '${medication.dosage} • ${medication.frequency}',
                    style: TextStyle(
                      fontSize: 14,
                      color: AppColors.textSecondary,
                    ),
                  ),
                ],
              ),
            ),
            Icon(Icons.chevron_right, color: AppColors.textTertiary, size: 24),
          ],
        ),
      ),
    );
  }

  String _formatTime(DateTime time) {
    final hour = time.hour > 12
        ? time.hour - 12
        : (time.hour == 0 ? 12 : time.hour);
    final minute = time.minute.toString().padLeft(2, '0');
    final period = time.hour >= 12 ? 'PM' : 'AM';
    return '$hour:$minute $period';
  }

  Future<void> _handleMarkTaken(int medId, MedicationProvider provider) async {
    final success = await provider.markAsTaken(medId);
    if (success && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Row(
            children: [
              Icon(Icons.check_circle, color: Colors.white),
              const SizedBox(width: 12),
              Text('Medication marked as taken'),
            ],
          ),
          backgroundColor: AppColors.success,
          behavior: SnackBarBehavior.floating,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
          ),
        ),
      );
    }
  }

  Future<void> _handleSkip(int medId, MedicationProvider provider) async {
    final controller = TextEditingController();
    final result = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        title: const Text('Skip Medication'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text('Please provide a reason:'),
            const SizedBox(height: 16),
            TextField(
              controller: controller,
              decoration: InputDecoration(
                hintText: 'Reason for skipping',
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
              ),
              maxLines: 3,
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(context, true),
            style: ElevatedButton.styleFrom(
              backgroundColor: AppColors.error,
              foregroundColor: Colors.white,
            ),
            child: const Text('Skip'),
          ),
        ],
      ),
    );

    if (result == true) {
      final success = await provider.skipMedication(medId, controller.text);
      if (success && mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Medication skipped'),
            backgroundColor: AppColors.alert,
            behavior: SnackBarBehavior.floating,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(16),
            ),
          ),
        );
      }
    }
  }
}
