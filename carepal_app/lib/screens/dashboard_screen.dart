import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';
import 'package:intl/intl.dart';
import '../core/app_colors.dart';
import '../providers/auth_provider.dart';
import '../providers/dashboard_provider.dart';
import '../providers/vitals_provider.dart';
import '../providers/medication_provider.dart';
import '../widgets/carepal_logo.dart';
import '../widgets/loading_shimmer.dart';
import '../widgets/error_view.dart';
import 'profile/profile_screen.dart';
import 'analytics/analytics_screen.dart';
import 'ai_agent/ai_voice_screen.dart';
import 'vitals/vitals_detail_screen.dart';
import '../widgets/quick_vital_entry.dart';

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

class _HomeTab extends StatefulWidget {
  final String name;
  final VoidCallback onRefresh;

  const _HomeTab({required this.name, required this.onRefresh});

  @override
  State<_HomeTab> createState() => _HomeTabState();
}

class _HomeTabState extends State<_HomeTab> {
  late Stream<DateTime> _timerStream;

  @override
  void initState() {
    super.initState();
    _timerStream = Stream.periodic(
      const Duration(seconds: 1),
      (_) => DateTime.now(),
    );
  }

  @override
  Widget build(BuildContext context) {
    return RefreshIndicator(
      onRefresh: () async => widget.onRefresh(),
      color: AppColors.primary,
      child: SingleChildScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _buildStatusBar(),
            const SizedBox(height: 32),
            _buildGreeting(),
            const SizedBox(height: 32),
            _buildVitalsGrid(context),
            const SizedBox(height: 24),
            _buildMedicationPanel(context),
            const SizedBox(height: 40),
            _buildVoiceAssistantTrigger(context),
            const SizedBox(height: 100),
          ],
        ),
      ),
    );
  }

  Widget _buildStatusBar() {
    return StreamBuilder<DateTime>(
      stream: _timerStream,
      builder: (context, snapshot) {
        final time = snapshot.data ?? DateTime.now();
        final timeStr = DateFormat('hh:mm a').format(time);

        return Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            // Status
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(20),
                border: Border.all(
                  color: AppColors.primaryLight.withOpacity(0.3),
                ),
              ),
              child: Row(
                children: [
                  Container(
                    width: 8,
                    height: 8,
                    decoration: const BoxDecoration(
                      color: AppColors.success,
                      shape: BoxShape.circle,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Text(
                    'PAL Connected',
                    style: TextStyle(
                      color: AppColors.primaryDark,
                      fontWeight: FontWeight.w600,
                      fontSize: 12,
                    ),
                  ),
                ],
              ),
            ),

            // Time
            Text(
              timeStr,
              style: TextStyle(
                fontSize: 24,
                fontWeight: FontWeight.bold,
                color: AppColors.primaryDark,
              ),
            ),

            // Actions
            Row(
              children: [
                Stack(
                  children: [
                    Icon(
                      Icons.notifications_outlined,
                      color: AppColors.primary,
                      size: 28,
                    ),
                    Positioned(
                      top: 0,
                      right: 0,
                      child: Container(
                        width: 10,
                        height: 10,
                        decoration: BoxDecoration(
                          color: AppColors.alert,
                          shape: BoxShape.circle,
                          border: Border.all(
                            color: AppColors.background,
                            width: 2,
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(width: 16),
                Container(
                  padding: const EdgeInsets.all(4),
                  decoration: BoxDecoration(
                    color: AppColors.primaryLighter,
                    shape: BoxShape.circle,
                  ),
                  child: Icon(
                    Icons.person,
                    color: AppColors.primaryDark,
                    size: 24,
                  ),
                ),
              ],
            ),
          ],
        );
      },
    );
  }

  Widget _buildGreeting() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const CarePalLogo(size: 40, showText: true),
        const SizedBox(height: 16),
        Text(
          'Good morning, ${widget.name}',
          style: GoogleFonts.lexend(
            fontSize: 32,
            fontWeight: FontWeight.bold,
            color: AppColors.primaryDark,
            height: 1.1,
          ),
        ),
        const SizedBox(height: 8),
        Text(
          "I'm ready for our daily check-in.",
          style: TextStyle(
            fontSize: 18,
            color: AppColors.primary.withOpacity(0.8),
            fontWeight: FontWeight.w500,
          ),
        ),
      ],
    );
  }

  Widget _buildVitalsGrid(BuildContext context) {
    return Consumer<DashboardProvider>(
      builder: (context, provider, _) {
        final vitals = provider.vitalsSummary ?? {};

        return Column(
          children: [
            Row(
              children: [
                Expanded(
                  child: _buildVitalCard(
                    context,
                    'HR',
                    'Heart Rate',
                    vitals['HR'],
                    Icons.favorite,
                    AppColors.vitalsRed,
                    'bpm',
                  ),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: _buildVitalCard(
                    context,
                    'BP',
                    'Biomedical Pressure', // Adjusted name
                    vitals['BP'],
                    Icons.monitor_heart,
                    AppColors.vitalsBlue,
                    'mmHg',
                    isBp: true,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            Row(
              children: [
                Expanded(
                  child: _buildVitalCard(
                    context,
                    'TEMP',
                    'Temperature',
                    vitals['TEMP'],
                    Icons.thermostat,
                    AppColors.vitalsOrange,
                    '°F',
                  ),
                ),
                const SizedBox(width: 16),
                Expanded(child: _buildMeasureNowCard(context)),
              ],
            ),
          ],
        );
      },
    );
  }

  Widget _buildVitalCard(
    BuildContext context,
    String code,
    String name,
    dynamic summary,
    IconData icon,
    Color color,
    String unit, {
    bool isBp = false,
  }) {
    String value = '--';
    String status = 'Normal';
    Color statusColor = AppColors.success;
    Color iconBgColor = color.withOpacity(0.1);

    if (summary?.latestReading != null) {
      final latest = summary.latestReading;
      if (isBp && latest['values'] != null) {
        final double s = (latest['values']['systolic'] as num).toDouble();
        final double d = (latest['values']['diastolic'] as num).toDouble();
        value = '${s.toInt()}/${d.toInt()}';

        if (s > 140 || d > 90) {
          status = 'High';
          statusColor = AppColors.error;
        } else if (s > 130 || d > 85) {
          status = 'Elevated';
          statusColor = AppColors.warning;
        }
      } else if (latest['value'] != null) {
        final double val = (latest['value'] as num).toDouble();
        value = val.toString();

        // Simple logic for demo
        if (code == 'HR' && val > 100) {
          status = 'High';
          statusColor = AppColors.alert;
        }
        if (code == 'TEMP' && val > 99.5) {
          status = 'Fever';
          statusColor = AppColors.alert;
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
        height: 180,
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(24),
          border: Border.all(color: AppColors.primaryLight.withOpacity(0.3)),
          boxShadow: [
            BoxShadow(
              color: AppColors.primary.withOpacity(0.05),
              blurRadius: 10,
              offset: const Offset(0, 4),
            ),
          ],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: iconBgColor,
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: Icon(icon, color: color, size: 24),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 8,
                    vertical: 4,
                  ),
                  decoration: BoxDecoration(
                    color: statusColor.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Text(
                    status.toUpperCase(),
                    style: TextStyle(
                      fontSize: 10,
                      fontWeight: FontWeight.bold,
                      color: statusColor,
                    ),
                  ),
                ),
              ],
            ),
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                RichText(
                  text: TextSpan(
                    children: [
                      TextSpan(
                        text: value,
                        style: GoogleFonts.lexend(
                          fontSize: 32,
                          fontWeight: FontWeight.bold,
                          color: AppColors.primaryDark,
                        ),
                      ),
                      TextSpan(
                        text: ' $unit',
                        style: TextStyle(
                          fontSize: 14,
                          color: AppColors.textTertiary,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  name,
                  style: TextStyle(
                    fontSize: 14,
                    color: AppColors.textSecondary,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildMeasureNowCard(BuildContext context) {
    return GestureDetector(
      onTap: () {
        showModalBottomSheet(
          context: context,
          isScrollControlled: true,
          backgroundColor: Colors.transparent,
          builder: (_) => const QuickVitalEntry(),
        );
      },
      child: Container(
        height: 180,
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          color: AppColors.primary,
          borderRadius: BorderRadius.circular(24),
          boxShadow: [
            BoxShadow(
              color: AppColors.primary.withOpacity(0.3),
              blurRadius: 10,
              offset: const Offset(0, 4),
            ),
          ],
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Colors.white.withOpacity(0.2),
                shape: BoxShape.circle,
              ),
              child: const Icon(Icons.add, color: Colors.white, size: 32),
            ),
            const SizedBox(height: 16),
            const Text(
              'Measure Vitals Now',
              textAlign: TextAlign.center,
              style: TextStyle(
                color: Colors.white,
                fontSize: 18,
                fontWeight: FontWeight.bold,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildMedicationPanel(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(32),
        border: Border.all(color: AppColors.primaryLight.withOpacity(0.3)),
        boxShadow: [
          BoxShadow(
            color: AppColors.primary.withOpacity(0.05),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'Medicines',
                style: GoogleFonts.lexend(
                  fontSize: 20,
                  fontWeight: FontWeight.bold,
                  color: AppColors.primaryDark,
                ),
              ),
              Icon(Icons.calendar_today, color: AppColors.primaryLight),
            ],
          ),
          const SizedBox(height: 20),
          Consumer<MedicationProvider>(
            builder: (context, provider, _) {
              if (provider.todaysSchedule.isEmpty) {
                return const Center(
                  child: Padding(
                    padding: EdgeInsets.all(16.0),
                    child: Text("No medications due today"),
                  ),
                );
              }
              // Show first 3
              final meds = provider.todaysSchedule.take(3).toList();

              return Column(
                children: meds.map((med) {
                  bool isTaken = med.isTaken;
                  // "Due" logic could be refined (e.g. check time), but simplified here:
                  bool isDue = !isTaken;

                  return Container(
                    margin: const EdgeInsets.only(bottom: 12),
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: isTaken
                          ? AppColors.primaryLight.withOpacity(0.1)
                          : (isDue
                                ? AppColors.alert.withOpacity(0.05)
                                : Colors.grey[50]),
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(
                        color: isTaken
                            ? AppColors.primaryLight
                            : (isDue
                                  ? AppColors.alert.withOpacity(0.3)
                                  : Colors.grey[200]!),
                      ),
                    ),
                    child: Row(
                      children: [
                        Container(
                          width: 12,
                          height: 12,
                          decoration: BoxDecoration(
                            color: isTaken
                                ? AppColors.primary
                                : (isDue ? AppColors.alert : Colors.grey),
                            shape: BoxShape.circle,
                          ),
                        ),
                        const SizedBox(width: 16),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                med.medication.medicationName,
                                style: const TextStyle(
                                  fontSize: 16,
                                  fontWeight: FontWeight.bold,
                                  color: AppColors.primaryDark,
                                ),
                              ),
                              Text(
                                DateFormat('hh:mm a').format(med.scheduledTime),
                                style: const TextStyle(
                                  fontSize: 14,
                                  color: AppColors.textSecondary,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  );
                }).toList(),
              );
            },
          ),
        ],
      ),
    );
  }

  Widget _buildVoiceAssistantTrigger(BuildContext context) {
    return Center(
      child: Column(
        children: [
          GestureDetector(
            onTap: () {
              Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => const AIVoiceScreen()),
              );
            },
            child: Stack(
              alignment: Alignment.center,
              children: [
                // Pulse effect (static for now, could be animated)
                Container(
                  width: 80,
                  height: 80,
                  decoration: BoxDecoration(
                    color: AppColors.primary.withOpacity(0.2),
                    shape: BoxShape.circle,
                  ),
                ),
                Container(
                  width: 64,
                  height: 64,
                  decoration: BoxDecoration(
                    color: AppColors.primary.withOpacity(0.4),
                    shape: BoxShape.circle,
                  ),
                ),
                Container(
                  width: 50,
                  height: 50,
                  decoration: BoxDecoration(
                    color: AppColors.primary,
                    shape: BoxShape.circle,
                    boxShadow: [
                      BoxShadow(
                        color: AppColors.primary.withOpacity(0.4),
                        blurRadius: 15,
                        offset: const Offset(0, 5),
                      ),
                    ],
                  ),
                  child: const Icon(Icons.mic, color: Colors.white, size: 28),
                ),
              ],
            ),
          ),
          const SizedBox(height: 12),
          Text(
            'TAP TO SPEAK WITH PAL',
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.bold,
              letterSpacing: 1.2,
              color: AppColors.primaryDark.withOpacity(0.7),
            ),
          ),
        ],
      ),
    );
  }
}
