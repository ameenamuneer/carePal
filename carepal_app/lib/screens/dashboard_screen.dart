// lib/screens/dashboard_screen.dart
import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';
import '../core/app_colors.dart';
import '../providers/auth_provider.dart';
import '../providers/vitals_provider.dart';
import '../models/vital_reading.dart';
import '../providers/medication_provider.dart';
import '../widgets/carepal_logo.dart';
import '../widgets/loading_shimmer.dart';
import '../widgets/error_view.dart';
import '../widgets/quick_vital_entry.dart';
import 'package:fl_chart/fl_chart.dart';

import 'package:permission_handler/permission_handler.dart';

// Navigation Targets
import 'medications/medications_screen.dart';
import 'analytics/analytics_screen.dart';
import 'profile/profile_screen.dart';
import 'family/family_members_screen.dart';
import 'admin_test_page.dart';
import 'gemini_live_screen.dart';
import 'appointments/appointment_list_screen.dart';
import 'vitals/vitals_detail_screen.dart';

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
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _loadInitialData();
    });
  }

  Future<void> _loadInitialData() async {
    if (!mounted) return;

    setState(() {
      _isInitializing = true;
      _initError = null;
    });

    try {
      // Load essential data
      await Future.wait([
        context
            .read<VitalsProvider>()
            .loadDashboardVitals(), // FIXED: Use dedicated dashboard loader
        context.read<VitalsProvider>().loadVitalTypes(),
        context.read<MedicationProvider>().loadTodaysSchedule(),
        context.read<MedicationProvider>().loadAdherenceRate(days: 7),
      ]).timeout(const Duration(seconds: 30));

      if (mounted) {
        setState(() => _isInitializing = false);
      }

      // Request Bluetooth permissions
      await _requestPermissions();
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
    final isDesktop = MediaQuery.of(context).size.width >= 900;

    return Scaffold(
      backgroundColor: AppColors.background,
      body: Row(
        children: [
          if (isDesktop) _buildNavigationRail(),
          Expanded(
            child: _isInitializing
                ? _buildLoadingState()
                : _initError != null
                ? ErrorView(message: _initError!, onRetry: _loadInitialData)
                : _buildMainContent(),
          ),
        ],
      ),
      bottomNavigationBar: !isDesktop ? _buildBottomNavigationBar() : null,
      floatingActionButton: _selectedIndex == 0
          ? FloatingActionButton.extended(
              onPressed: () {
                showModalBottomSheet(
                  context: context,
                  isScrollControlled: true,
                  backgroundColor: Colors.transparent,
                  builder: (_) => const QuickVitalEntry(),
                ).then((result) {
                  if (result == true) {
                    _loadInitialData();
                  }
                });
              },
              label: const Text('Measure Vitals'),
              icon: const Icon(Icons.add),
              backgroundColor: AppColors.primary,
            )
          : null,
    );
  }

  Widget _buildMainContent() {
    // Mapping tabs to screens
    switch (_selectedIndex) {
      case 0:
        return _buildHomeOverview();
      case 1:
        return const MedicationsScreen();
      case 2:
        return const AnalyticsScreen();
      case 3:
        return const AppointmentListScreen();
      case 4:
        return const FamilyMembersScreen();
      case 5:
        return const ProfileScreen();
      default:
        return _buildHomeOverview();
    }
  }

  Widget _buildNavigationRail() {
    return NavigationRail(
      selectedIndex: _selectedIndex,
      onDestinationSelected: (int index) {
        setState(() {
          _selectedIndex = index;
        });
      },
      labelType: NavigationRailLabelType.all,
      leading: Padding(
        padding: const EdgeInsets.symmetric(vertical: 24),
        child: GestureDetector(
          onLongPress: () {
            print(
              "DashboardScreen: Long Press Detected! Navigating to AdminTestPage...",
            );
            Navigator.push(
              context,
              MaterialPageRoute(builder: (context) => const AdminTestPage()),
            );
          },
          child: const CarePalLogo(size: 32, showText: false),
        ),
      ),
      destinations: const [
        NavigationRailDestination(
          icon: Icon(Icons.dashboard_outlined),
          selectedIcon: Icon(Icons.dashboard),
          label: Text('Home'),
        ),
        NavigationRailDestination(
          icon: Icon(Icons.medication_outlined),
          selectedIcon: Icon(Icons.medication),
          label: Text('Meds'),
        ),
        NavigationRailDestination(
          icon: Icon(Icons.analytics_outlined),
          selectedIcon: Icon(Icons.analytics),
          label: Text('Trends'),
        ),

        NavigationRailDestination(
          icon: Icon(Icons.calendar_today_outlined),
          selectedIcon: Icon(Icons.calendar_today),
          label: Text('Visits'),
        ),
        NavigationRailDestination(
          icon: Icon(Icons.family_restroom_outlined),
          selectedIcon: Icon(Icons.family_restroom),
          label: Text('Family'),
        ),
        NavigationRailDestination(
          icon: Icon(Icons.person_outline),
          selectedIcon: Icon(Icons.person),
          label: Text('Profile'),
        ),
      ],
    );
  }

  Widget _buildBottomNavigationBar() {
    return NavigationBar(
      selectedIndex: _selectedIndex,
      onDestinationSelected: (int index) {
        setState(() {
          _selectedIndex = index;
        });
      },
      destinations: const [
        NavigationDestination(
          icon: Icon(Icons.dashboard_outlined),
          selectedIcon: Icon(Icons.dashboard),
          label: 'Home',
        ),
        NavigationDestination(
          icon: Icon(Icons.medication_outlined),
          selectedIcon: Icon(Icons.medication),
          label: 'Meds',
        ),
        NavigationDestination(
          icon: Icon(Icons.analytics_outlined),
          selectedIcon: Icon(Icons.analytics),
          label: 'Trends',
        ),
        NavigationDestination(
          icon: Icon(Icons.calendar_today_outlined),
          selectedIcon: Icon(Icons.calendar_today),
          label: 'Visits',
        ),
        NavigationDestination(
          icon: Icon(Icons.family_restroom_outlined),
          selectedIcon: Icon(Icons.family_restroom),
          label: 'Family',
        ),
        NavigationDestination(
          icon: Icon(Icons.person_outline),
          selectedIcon: Icon(Icons.person),
          label: 'Profile',
        ),
      ],
    );
  }

  Widget _buildHomeOverview() {
    final user = Provider.of<AuthProvider>(context).user;
    final firstName = user?['first_name'] ?? 'User';

    return RefreshIndicator(
      onRefresh: _loadInitialData,
      child: SingleChildScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _buildHeader(),
            const SizedBox(height: 24),
            _buildGeminiLiveCard(),
            const SizedBox(height: 24),
            _buildGreeting(firstName),
            const SizedBox(height: 32),
            _buildVitalsGridFromProvider(),
            const SizedBox(height: 24),
            _buildMedicationSummary(),
          ],
        ),
      ),
    );
  }

  Widget _buildLoadingState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          CircularProgressIndicator(color: AppColors.primary),
          const SizedBox(height: 16),
          Text(
            'Loading your health data...',
            style: TextStyle(fontSize: 16, color: AppColors.textSecondary),
          ),
        ],
      ),
    );
  }

  Widget _buildHeader() {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        // Only show logo text if no sidebar (mobile)
        if (MediaQuery.of(context).size.width < 900)
          GestureDetector(
            onLongPress: () {
              Navigator.push(
                context,
                MaterialPageRoute(builder: (context) => const AdminTestPage()),
              );
            },
            child: const CarePalLogo(size: 32, showText: true),
          )
        else
          // Placeholder for spacing if needed
          const SizedBox.shrink(),

        Row(
          children: [
            Icon(Icons.notifications_outlined, color: AppColors.primary),
            const SizedBox(width: 16),
            CircleAvatar(
              backgroundColor: AppColors.primaryLighter,
              child: Icon(Icons.person, color: AppColors.primaryDark),
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildGreeting(String firstName) {
    final hour = DateTime.now().hour;
    String greeting = hour < 12
        ? 'Good morning'
        : hour < 18
        ? 'Good afternoon'
        : 'Good evening';

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          '$greeting, $firstName',
          style: GoogleFonts.lexend(
            fontSize: 32,
            fontWeight: FontWeight.bold,
            color: AppColors.primaryDark,
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

  Widget _buildVitalsGridFromProvider() {
    return Consumer<VitalsProvider>(
      builder: (context, provider, _) {
        if (provider.isLoading && provider.dashboardSummaries.isEmpty) {
          return _buildVitalsLoadingGrid();
        }

        final summaries = provider.dashboardSummaries;

        return Column(
          children: [
            Row(
              children: [
                Expanded(
                  child: _buildVitalCardFromSummary(
                    'HR',
                    'Heart Rate',
                    summaries['HR'],
                    Icons.favorite,
                    AppColors.vitalsRed,
                  ),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: _buildVitalCardFromSummary(
                    'BP',
                    'Blood Pressure',
                    summaries['BP'],
                    Icons.monitor_heart,
                    AppColors.vitalsBlue,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            Row(
              children: [
                Expanded(
                  child: _buildVitalCardFromSummary(
                    'TEMP',
                    'Temperature',
                    summaries['TEMP'],
                    Icons.thermostat,
                    AppColors.vitalsOrange,
                  ),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: _buildVitalCardFromSummary(
                    'SPO2',
                    'Oxygen',
                    summaries['SPO2'],
                    Icons.air,
                    AppColors.vitalsBlue,
                  ),
                ),
              ],
            ),
          ],
        );
      },
    );
  }

  Widget _buildVitalCardFromSummary(
    String code,
    String name,
    Map<String, dynamic>? summary,
    IconData icon,
    Color color,
  ) {
    String value = '--';
    String status = 'Normal';
    Color statusColor = AppColors.success;
    List<dynamic> history = [];

    if (summary != null) {
      if (summary['latest_reading'] != null) {
        final reading = VitalReading.fromJson(summary['latest_reading']);
        value = reading.displayValue.split(' ')[0];
        status = reading.anomalySeverity == 'NORMAL' ? 'Normal' : 'Alert';
        statusColor = reading.anomalySeverity == 'NORMAL'
            ? AppColors.success
            : AppColors.error;
      }
      history = summary['recent_history'] ?? [];
    }

    // ... continue to card ...

    return GestureDetector(
      onTap: () {
        Navigator.push(
          context,
          MaterialPageRoute(
            builder: (context) => VitalsDetailScreen(
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
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(24),
          border: Border.all(color: color.withOpacity(0.1), width: 1),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: color.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Icon(icon, color: color, size: 24),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 12,
                    vertical: 6,
                  ),
                  decoration: BoxDecoration(
                    color: statusColor.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Text(
                    status.toUpperCase(),
                    style: TextStyle(
                      fontSize: 10,
                      fontWeight: FontWeight.w600,
                      color: statusColor,
                    ),
                  ),
                ),
              ],
            ),
            _buildSparkline(history, color),
            Text(
              value,
              style: GoogleFonts.lexend(
                fontSize: 32,
                fontWeight: FontWeight.bold,
                color: AppColors.textPrimary,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              name,
              style: TextStyle(fontSize: 14, color: AppColors.textSecondary),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildVitalsLoadingGrid() {
    return Column(
      children: [
        Row(
          children: [
            Expanded(child: LoadingShimmer(height: 180, borderRadius: 24)),
            const SizedBox(width: 16),
            Expanded(child: LoadingShimmer(height: 180, borderRadius: 24)),
          ],
        ),
        const SizedBox(height: 16),
        Row(
          children: [
            Expanded(child: LoadingShimmer(height: 180, borderRadius: 24)),
            const SizedBox(width: 16),
            Expanded(child: LoadingShimmer(height: 180, borderRadius: 24)),
          ],
        ),
      ],
    );
  }

  Widget _buildMedicationSummary() {
    return Consumer<MedicationProvider>(
      builder: (context, provider, _) {
        final scheduled = provider.scheduledMedications.length;
        final taken = provider.takenMedications.length;
        final adherence = provider.adherenceRate;

        return Container(
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
            color: AppColors.surface,
            borderRadius: BorderRadius.circular(24),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Icon(Icons.medication, color: AppColors.primary),
                  const SizedBox(width: 12),
                  Text(
                    'Medications Today',
                    style: TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.w600,
                      color: AppColors.textPrimary,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceAround,
                children: [
                  _buildMedStat('Scheduled', scheduled.toString()),
                  _buildMedStat('Taken', taken.toString()),
                  _buildMedStat(
                    'Adherence',
                    '${adherence.toStringAsFixed(0)}%',
                  ),
                ],
              ),
            ],
          ),
        );
      },
    );
  }

  Future<void> _requestPermissions() async {
    // Skip Bluetooth permissions on Web
    if (kIsWeb) return;

    // Android 12+ requires bluetoothScan and bluetoothConnect
    // Android 11- requires location
    Map<Permission, PermissionStatus> statuses = await [
      Permission.bluetoothScan,
      Permission.bluetoothConnect,
      Permission.location,
    ].request();

    if (statuses[Permission.bluetoothScan]?.isDenied == true ||
        statuses[Permission.bluetoothConnect]?.isDenied == true) {
      // Ideally show dialog to user explaining why
      debugPrint("Bluetooth permissions denied");
    }
  }

  Widget _buildMedStat(String label, String value) {
    return Column(
      children: [
        Text(
          value,
          style: TextStyle(
            fontSize: 24,
            fontWeight: FontWeight.bold,
            color: AppColors.primary,
          ),
        ),
        const SizedBox(height: 4),
        Text(
          label,
          style: TextStyle(fontSize: 12, color: AppColors.textSecondary),
        ),
      ],
    );
  }

  Widget _buildGeminiLiveCard() {
    return GestureDetector(
      onTap: () {
        Navigator.push(
          context,
          MaterialPageRoute(builder: (context) => const GeminiLiveScreen()),
        );
      },
      child: Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          gradient: const LinearGradient(
            colors: [
              Color(0xFF4285F4),
              Color(0xFF9C27B0),
            ], // Google Blue to Purple
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
          borderRadius: BorderRadius.circular(24),
          boxShadow: [
            BoxShadow(
              color: const Color(0xFF4285F4).withOpacity(0.3),
              blurRadius: 10,
              offset: const Offset(0, 4),
            ),
          ],
        ),
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.white.withOpacity(0.2),
                shape: BoxShape.circle,
              ),
              child: const Icon(Icons.videocam, color: Colors.white, size: 28),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: const [
                  Text(
                    "Talk to Gemini Live",
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  SizedBox(height: 4),
                  Text(
                    "Real-time video & audio chat",
                    style: TextStyle(color: Colors.white70, fontSize: 14),
                  ),
                ],
              ),
            ),
            const Icon(
              Icons.arrow_forward_ios,
              color: Colors.white70,
              size: 16,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSparkline(List<dynamic> history, Color color) {
    if (history.length < 2) return const Spacer();

    // Parse data points
    List<FlSpot> spots = [];
    double minY = double.infinity;
    double maxY = double.negativeInfinity;

    for (int i = 0; i < history.length; i++) {
      try {
        final r = history[i];
        // history is oldest->newest

        double val = 0;
        if (r['value'] != null) {
          val = (r['value'] as num).toDouble();
        } else if (r['values'] != null) {
          final values = r['values'] as Map<String, dynamic>;
          if (values.containsKey('systolic')) {
            val = (values['systolic'] as num).toDouble();
          } else if (values.values.isNotEmpty) {
            val = (values.values.first as num).toDouble();
          }
        }

        spots.add(FlSpot(i.toDouble(), val));
        if (val < minY) minY = val;
        if (val > maxY) maxY = val;
      } catch (e) {
        // Skip invalid
      }
    }

    if (spots.isEmpty) return const Spacer();

    // Add padding to Y range
    final range = maxY - minY;
    if (range == 0) {
      minY -= 5;
      maxY += 5;
    } else {
      minY -= range * 0.2;
      maxY += range * 0.2;
    }

    return Expanded(
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 8.0),
        child: LineChart(
          LineChartData(
            gridData: FlGridData(show: false),
            titlesData: FlTitlesData(show: false),
            borderData: FlBorderData(show: false),
            minX: 0,
            maxX: (history.length - 1).toDouble(),
            minY: minY,
            maxY: maxY,
            lineBarsData: [
              LineChartBarData(
                spots: spots,
                isCurved: true,
                color: color,
                barWidth: 2,
                isStrokeCapRound: true,
                dotData: FlDotData(show: false),
                belowBarData: BarAreaData(
                  show: true,
                  color: color.withOpacity(0.1),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
