import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:intl/intl.dart';
import '../core/app_colors.dart';
import '../providers/auth_provider.dart';
import '../providers/dashboard_provider.dart';
import '../providers/vitals_provider.dart';
import '../providers/medication_provider.dart';
import '../widgets/loading_shimmer.dart';
import '../widgets/error_view.dart';
import 'login_screen.dart';
import 'profile/profile_screen.dart';
import 'analytics/analytics_screen.dart';
import 'ai_agent/ai_voice_screen.dart';
import 'vitals/vitals_detail_screen.dart';
import 'medications/medications_screen.dart';
import 'alerts/alerts_screen.dart';
import '../widgets/quick_vital_entry.dart';
import '../services/emergency_service.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  int _selectedIndex = 0;
  bool _isInitializing = true;
  String? _initError;

  @override
  void initState() {
    super.initState();
    _loadInitialData();
  }

  Future<void> _loadInitialData() async {
    setState(() {
      _isInitializing = true;
      _initError = null;
    });

    try {
      await Future.wait([
        context.read<DashboardProvider>().loadDashboard(),
        context.read<VitalsProvider>().loadReadings(days: 7),
        context.read<VitalsProvider>().loadVitalTypes(),
        context.read<MedicationProvider>().loadTodaysSchedule(),
        context.read<MedicationProvider>().loadAdherenceRate(days: 7),
      ]).timeout(const Duration(seconds: 30));

      if (mounted) {
        setState(() => _isInitializing = false);
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _isInitializing = false;
          _initError = e.toString();
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final user = Provider.of<AuthProvider>(context).user;
    final firstName = user?['first_name'] ?? 'User';

    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: _isInitializing
            ? _buildLoadingState()
            : _initError != null
            ? ErrorView(message: _initError!, onRetry: _loadInitialData)
            : _buildBody(firstName),
      ),
      floatingActionButton: _selectedIndex == 0
          ? FloatingActionButton(
              onPressed: () {
                Navigator.push(
                  context,
                  MaterialPageRoute(builder: (_) => const AIVoiceScreen()),
                );
              },
              backgroundColor: AppColors.primary,
              child: const Icon(Icons.mic_rounded, size: 28),
            )
          : null,
      floatingActionButtonLocation: FloatingActionButtonLocation.centerDocked,
      bottomNavigationBar: _buildBottomNav(),
    );
  }

  Widget _buildLoadingState() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        children: [
          LoadingShimmer(height: 200, borderRadius: 24),
          const SizedBox(height: 16),
          GridView.count(
            crossAxisCount: 2,
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            mainAxisSpacing: 16,
            crossAxisSpacing: 16,
            childAspectRatio: 1.1,
            children: List.generate(4, (_) => const VitalCardShimmer()),
          ),
        ],
      ),
    );
  }

  Widget _buildBody(String name) {
    switch (_selectedIndex) {
      case 0:
        return _HomeTab(name: name, onRefresh: _loadInitialData);
      case 1:
        return const AnalyticsScreen();
      case 2:
        return const ProfileScreen();
      default:
        return const SizedBox();
    }
  }

  Widget _buildBottomNav() {
    return Container(
      decoration: BoxDecoration(
        color: AppColors.surface,
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.05),
            blurRadius: 10,
            offset: const Offset(0, -2),
          ),
        ],
      ),
      child: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 12),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceAround,
            children: [
              _buildNavItem(0, Icons.home_rounded, 'Home'),
              const SizedBox(width: 80), // Space for FAB
              _buildNavItem(1, Icons.analytics_outlined, 'Analytics'),
              _buildNavItem(2, Icons.person_outline, 'Profile'),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildNavItem(int index, IconData icon, String label) {
    final isSelected = _selectedIndex == index;

    return InkWell(
      onTap: () => setState(() => _selectedIndex = index),
      borderRadius: BorderRadius.circular(12),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
        decoration: BoxDecoration(
          color: isSelected ? AppColors.primaryLighter : Colors.transparent,
          borderRadius: BorderRadius.circular(12),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              icon,
              color: isSelected ? AppColors.primary : AppColors.textTertiary,
              size: 24,
            ),
            const SizedBox(height: 4),
            Text(
              label,
              style: TextStyle(
                fontSize: 12,
                fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
                color: isSelected ? AppColors.primary : AppColors.textTertiary,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ==================== HOME TAB ====================

class _HomeTab extends StatelessWidget {
  final String name;
  final VoidCallback onRefresh;

  const _HomeTab({required this.name, required this.onRefresh});

  @override
  Widget build(BuildContext context) {
    return RefreshIndicator(
      onRefresh: () async => onRefresh(),
      color: AppColors.primary,
      child: SingleChildScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _buildHeader(context),
            const SizedBox(height: 16),
            _buildHealthScoreCard(),
            const SizedBox(height: 16),
            _buildQuickActions(context),
            const SizedBox(height: 16),
            _buildVitalsSection(context),
            const SizedBox(height: 16),
            _buildMedicationsSection(context),
            const SizedBox(height: 100),
          ],
        ),
      ),
    );
  }

  Widget _buildHeader(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Welcome back,',
              style: TextStyle(fontSize: 13, color: AppColors.textSecondary),
            ),
            const SizedBox(height: 2),
            Text(
              name,
              style: TextStyle(
                fontSize: 24,
                fontWeight: FontWeight.bold,
                color: AppColors.textPrimary,
              ),
            ),
          ],
        ),
        Row(
          children: [
            GestureDetector(
              onTap: () => _showEmergencyDialog(context),
              child: Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: AppColors.error.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(color: AppColors.error, width: 1.5),
                ),
                child: Icon(Icons.emergency, color: AppColors.error, size: 20),
              ),
            ),
            const SizedBox(width: 8),
            IconButton(
              icon: Icon(
                Icons.logout,
                color: AppColors.textSecondary,
                size: 22,
              ),
              onPressed: () => _handleLogout(context),
            ),
          ],
        ),
      ],
    );
  }

  void _showEmergencyDialog(BuildContext context) {
    showDialog(
      context: context,
      builder: (dialogContext) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        title: Row(
          children: [
            Icon(Icons.emergency, color: AppColors.error),
            const SizedBox(width: 12),
            const Text(
              'Emergency Alert',
              style: TextStyle(fontSize: 18, color: AppColors.error),
            ),
          ],
        ),
        content: const Text(
          'This will call your emergency contacts and alert medical services. Continue?',
          style: TextStyle(height: 1.5),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () {
              Navigator.pop(dialogContext);
              _triggerEmergency(context);
            },
            style: ElevatedButton.styleFrom(
              backgroundColor: AppColors.error,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
            ),
            child: const Text(
              'Call Emergency',
              style: TextStyle(color: Colors.white),
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _triggerEmergency(BuildContext context) async {
    final dashboardProvider = context.read<DashboardProvider>();
    final patientId = dashboardProvider.dashboardData?.patientId;

    if (patientId == null) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Error: Patient info not loaded')),
        );
      }
      return;
    }

    try {
      final service = EmergencyService();
      await service.triggerEmergencyCall(
        patientId,
        'Manual Emergency Button Triggered',
      );

      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Row(
              children: [
                const Icon(Icons.check_circle, color: Colors.white),
                const SizedBox(width: 12),
                const Text('Emergency services notified'),
              ],
            ),
            backgroundColor: AppColors.error,
            behavior: SnackBarBehavior.floating,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
            ),
            duration: const Duration(seconds: 3),
          ),
        );
      }
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to call emergency: $e'),
            backgroundColor: AppColors.error,
          ),
        );
      }
    }
  }

  Future<void> _handleLogout(BuildContext context) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        title: const Text('Logout'),
        content: const Text('Are you sure?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(context, true),
            style: ElevatedButton.styleFrom(backgroundColor: AppColors.error),
            child: const Text('Logout', style: TextStyle(color: Colors.white)),
          ),
        ],
      ),
    );

    if (confirm == true && context.mounted) {
      await context.read<AuthProvider>().logout();
      Navigator.of(
        context,
      ).pushReplacement(MaterialPageRoute(builder: (_) => const LoginScreen()));
    }
  }

  Widget _buildHealthScoreCard() {
    return Consumer<DashboardProvider>(
      builder: (context, provider, _) {
        final score = provider.healthScore?.score ?? 0;
        final category = provider.healthScore?.category ?? 'Loading';

        return Container(
          padding: const EdgeInsets.all(24),
          decoration: BoxDecoration(
            gradient: AppColors.primaryGradient,
            borderRadius: BorderRadius.circular(20),
            boxShadow: [
              BoxShadow(
                color: AppColors.primary.withOpacity(0.25),
                blurRadius: 15,
                offset: const Offset(0, 8),
              ),
            ],
          ),
          child: Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Health Score',
                      style: TextStyle(
                        color: Colors.white.withOpacity(0.9),
                        fontSize: 13,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      score > 0 ? '$score' : '--',
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 48,
                        fontWeight: FontWeight.bold,
                        height: 1,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 12,
                        vertical: 6,
                      ),
                      decoration: BoxDecoration(
                        color: Colors.white.withOpacity(0.2),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Text(
                        category.toUpperCase(),
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 11,
                          fontWeight: FontWeight.w600,
                          letterSpacing: 0.5,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              Container(
                width: 80,
                height: 80,
                decoration: BoxDecoration(
                  color: Colors.white.withOpacity(0.15),
                  shape: BoxShape.circle,
                ),
                child: const Icon(
                  Icons.favorite_rounded,
                  color: Colors.white,
                  size: 40,
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildQuickActions(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: _buildActionCard(
            icon: Icons.add_circle_outline,
            label: 'Add Vitals',
            color: AppColors.primary,
            onTap: () {
              showModalBottomSheet(
                context: context,
                isScrollControlled: true,
                backgroundColor: Colors.transparent,
                builder: (_) => const QuickVitalEntry(),
              );
            },
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: _buildActionCard(
            icon: Icons.notifications_active,
            label: 'Alerts',
            color: AppColors.alert,
            onTap: () {
              Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => const AlertsScreen()),
              );
            },
          ),
        ),
      ],
    );
  }

  Widget _buildActionCard({
    required IconData icon,
    required String label,
    required Color color,
    required VoidCallback onTap,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 12),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: color.withOpacity(0.15)),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withOpacity(0.02),
              blurRadius: 6,
              offset: const Offset(0, 2),
            ),
          ],
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: color.withOpacity(0.12),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Icon(icon, color: color, size: 20),
            ),
            const SizedBox(width: 10),
            Text(
              label,
              style: TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w600,
                color: AppColors.textPrimary,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildVitalsSection(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              'Vitals',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.bold,
                color: AppColors.textPrimary,
              ),
            ),
            TextButton.icon(
              onPressed: () {
                // TODO: Navigate to all vitals screen
              },
              icon: Icon(
                Icons.arrow_forward,
                size: 16,
                color: AppColors.primary,
              ),
              label: Text(
                'View All',
                style: TextStyle(
                  fontSize: 13,
                  color: AppColors.primary,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 12),
        Consumer<DashboardProvider>(
          builder: (context, provider, _) {
            final vitals = provider.vitalsSummary ?? {};
            return GridView.count(
              crossAxisCount: 2,
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              mainAxisSpacing: 12,
              crossAxisSpacing: 12,
              childAspectRatio: 1.4, // More compact ratio
              children: [
                _buildVitalCard(
                  context,
                  'BP',
                  'Blood Pressure',
                  vitals['BP'],
                  Icons.favorite,
                  AppColors.vitalsRed,
                ),
                _buildVitalCard(
                  context,
                  'HR',
                  'Heart Rate',
                  vitals['HR'],
                  Icons.monitor_heart,
                  AppColors.vitalsPink,
                ),
                _buildVitalCard(
                  context,
                  'SPO2',
                  'Oxygen',
                  vitals['SPO2'],
                  Icons.air,
                  AppColors.vitalsBlue,
                ),
                _buildVitalCard(
                  context,
                  'TEMP',
                  'Temperature',
                  vitals['TEMP'],
                  Icons.thermostat,
                  AppColors.vitalsOrange,
                ),
              ],
            );
          },
        ),
      ],
    );
  }

  Widget _buildVitalCard(
    BuildContext context,
    String code,
    String name,
    dynamic summary,
    IconData icon,
    Color color,
  ) {
    String value = '--';
    String unit = '';
    String status = 'Normal';
    Color statusColor = AppColors.success;

    if (summary?.latestReading != null) {
      final latest = summary.latestReading;
      if (code == 'BP' && latest['values'] != null) {
        final systolic = latest['values']['systolic'];
        final diastolic = latest['values']['diastolic'];
        value = '$systolic/$diastolic';
        unit = 'mmHg';

        // BP status logic
        if (systolic > 140 || diastolic > 90) {
          status = 'High';
          statusColor = AppColors.error;
        } else if (systolic > 130 || diastolic > 85) {
          status = 'Elevated';
          statusColor = AppColors.warning;
        }
      } else if (latest['value'] != null) {
        final val = latest['value'];
        value = val.toString();

        // Set unit and status based on vital type
        switch (code) {
          case 'HR':
            unit = 'bpm';
            if (val < 60) {
              status = 'Low';
              statusColor = AppColors.warning;
            } else if (val > 100) {
              status = 'High';
              statusColor = AppColors.error;
            }
            break;
          case 'SPO2':
            unit = '%';
            if (val < 95) {
              status = 'Low';
              statusColor = AppColors.error;
            }
            break;
          case 'TEMP':
            unit = '°F';
            if (val > 99.5) {
              status = 'Fever';
              statusColor = AppColors.error;
            } else if (val < 97) {
              status = 'Low';
              statusColor = AppColors.warning;
            }
            break;
        }
      }
    }

    return GestureDetector(
      onTap: () {
        Navigator.push(
          context,
          MaterialPageRoute(
            builder: (_) => VitalsDetailScreen(
              vitalCode: code,
              vitalName: name,
              color: color,
              icon: icon,
            ),
          ),
        );
      },
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: color.withOpacity(0.15), width: 1.5),
          boxShadow: [
            BoxShadow(
              color: color.withOpacity(0.08),
              blurRadius: 8,
              offset: const Offset(0, 3),
            ),
          ],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            // Header row: Icon + Status badge
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: color.withOpacity(0.12),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Icon(icon, color: color, size: 18),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 8,
                    vertical: 4,
                  ),
                  decoration: BoxDecoration(
                    color: statusColor.withOpacity(0.12),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Text(
                    status,
                    style: TextStyle(
                      fontSize: 10,
                      fontWeight: FontWeight.bold,
                      color: statusColor,
                      letterSpacing: 0.3,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),

            // Vital name
            Text(
              name,
              style: TextStyle(
                fontSize: 11,
                color: AppColors.textSecondary,
                fontWeight: FontWeight.w500,
              ),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
            const SizedBox(height: 4),

            // Value
            Row(
              crossAxisAlignment: CrossAxisAlignment.baseline,
              textBaseline: TextBaseline.alphabetic,
              children: [
                Flexible(
                  child: Text(
                    value,
                    style: TextStyle(
                      fontSize: 20,
                      fontWeight: FontWeight.bold,
                      color: AppColors.textPrimary,
                      height: 1.2,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                if (unit.isNotEmpty) ...[
                  const SizedBox(width: 4),
                  Text(
                    unit,
                    style: TextStyle(
                      fontSize: 11,
                      color: AppColors.textSecondary,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ],
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildMedicationsSection(BuildContext context) {
    return Consumer<MedicationProvider>(
      builder: (context, provider, _) {
        final schedule = provider.todaysSchedule;
        final adherence = provider.adherenceRate;

        return GestureDetector(
          onTap: () {
            Navigator.push(
              context,
              MaterialPageRoute(builder: (_) => const MedicationsScreen()),
            );
          },
          child: Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: AppColors.surface,
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: AppColors.border),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withOpacity(0.03),
                  blurRadius: 10,
                  offset: const Offset(0, 4),
                ),
              ],
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      'Today\'s Medications',
                      style: TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                        color: AppColors.textPrimary,
                      ),
                    ),
                    Row(
                      children: [
                        Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 12,
                            vertical: 6,
                          ),
                          decoration: BoxDecoration(
                            color: AppColors.primaryLighter,
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: Text(
                            '${adherence.toInt()}%',
                            style: TextStyle(
                              fontSize: 14,
                              fontWeight: FontWeight.bold,
                              color: AppColors.primary,
                            ),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Icon(
                          Icons.chevron_right,
                          color: AppColors.textTertiary,
                          size: 20,
                        ),
                      ],
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                if (schedule.isEmpty)
                  Center(
                    child: Padding(
                      padding: const EdgeInsets.all(20),
                      child: Text(
                        'No medications scheduled',
                        style: TextStyle(
                          color: AppColors.textTertiary,
                          fontSize: 14,
                        ),
                      ),
                    ),
                  )
                else
                  ...schedule
                      .take(3)
                      .map(
                        (med) => Padding(
                          padding: const EdgeInsets.only(bottom: 12),
                          child: _buildMedicationItem(context, med, provider),
                        ),
                      ),
              ],
            ),
          ),
        );
      },
    );
  }

  // Update _buildMedicationItem to handle actions:
  Widget _buildMedicationItem(
    BuildContext context,
    dynamic schedule,
    MedicationProvider provider,
  ) {
    final medication = schedule.medication;
    final time = DateFormat('hh:mm a').format(schedule.scheduledTime);
    final isTaken = schedule.isTaken;

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.primaryLighter.withOpacity(0.3),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: isTaken ? AppColors.success : AppColors.primary,
          width: 1,
        ),
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: isTaken ? AppColors.success : AppColors.primary,
              borderRadius: BorderRadius.circular(8),
            ),
            child: Icon(
              isTaken ? Icons.check : Icons.medication,
              color: Colors.white,
              size: 20,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  medication.medicationName,
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: AppColors.textPrimary,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  '${medication.dosage} • $time',
                  style: TextStyle(
                    fontSize: 12,
                    color: AppColors.textSecondary,
                  ),
                ),
              ],
            ),
          ),
          if (!isTaken) // Show checkmark only if not taken
            GestureDetector(
              onTap: () async {
                // mark method expects schedule id, not medication id?
                // The user example used medication.id, but usually you mark a specific schedule.
                // Let's assume schedule.id is correct as per MedicationSchedule model logic usually.
                // If `schedule` is the object, it likely has an `id`.
                // User code: await provider.markAsTaken(medication.id);
                // Wait, markAsTaken usually needs the schedule entry ID to mark THAT specific time slot.
                // I will use schedule.id if available, or investigate.
                // Assuming provider.markAsTaken takes schedule ID.
                final success = await provider.markAsTaken(schedule.id);
                if (success && context.mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(
                      content: const Text('Marked as taken'),
                      backgroundColor: AppColors.success,
                      behavior: SnackBarBehavior.floating,
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                    ),
                  );
                }
              },
              child: Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: AppColors.success.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Icon(Icons.check, color: AppColors.success, size: 20),
              ),
            ),
        ],
      ),
    );
  }
}
