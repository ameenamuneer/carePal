import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:font_awesome_flutter/font_awesome_flutter.dart';
import '../core/app_colors.dart';
import '../services/dashboard_service.dart';
import '../services/medication_service.dart';
import '../models/dashboard_data.dart';
import '../providers/auth_provider.dart';
import 'medications/medications_screen.dart';
import 'family/family_members_screen.dart';
import 'vitals/vitals_detail_screen.dart';
import 'login_screen.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  int _selectedIndex = 0;
  final DashboardService _dashboardService = DashboardService();
  final MedicationService _medicationService = MedicationService();
  DashboardData? _data;
  bool _isLoading = true;
  String? _error;

  // Dashboard helper properties
  List<dynamic> _medications = [];

  @override
  void initState() {
    super.initState();
    _loadDashboard();
  }

  Future<void> _loadDashboard() async {
    try {
      setState(() {
        _isLoading = true;
        _error = null;
      });

      // Load dashboard data and medications in parallel
      final results = await Future.wait([
        _dashboardService.getDashboard(),
        _medicationService.getTodaysSchedule(),
      ]);

      if (mounted) {
        setState(() {
          _data = results[0] as DashboardData;
          _medications = (results[1] as List)
              .map(
                (s) => {
                  'id': s.medicationId,
                  'name': s.medicationName,
                  'dosage': s.dosage,
                  'time':
                      '${s.scheduledAt.hour.toString().padLeft(2, '0')}:${s.scheduledAt.minute.toString().padLeft(2, '0')}',
                  'taken': s.isTaken,
                },
              )
              .toList();
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = e.toString();
          _isLoading = false;
        });
      }
    }
  }

  Future<void> _markAsTaken(int medId) async {
    try {
      await _medicationService.logAdherence(
        medicationId: medId,
        status: 'TAKEN',
      );
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: const Text('Medication marked as taken'),
            backgroundColor: AppColors.success,
            behavior: SnackBarBehavior.floating,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(16),
            ),
          ),
        );
        _loadDashboard();
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to update: $e'),
            backgroundColor: AppColors.error,
          ),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final user = Provider.of<AuthProvider>(context).user;
    final firstName = user?['first_name'] ?? 'User';

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: AppColors.surface,
        elevation: 0,
        title: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              FontAwesomeIcons.heartPulse,
              color: AppColors.primary,
              size: 20,
            ),
            const SizedBox(width: 8),
            Text(
              'CarePAL',
              style: TextStyle(
                color: AppColors.primary,
                fontWeight: FontWeight.bold,
              ),
            ),
          ],
        ),
        actions: [
          IconButton(
            icon: Icon(Icons.refresh, color: AppColors.textPrimary),
            onPressed: _loadDashboard,
          ),
          IconButton(
            icon: Icon(Icons.logout, color: AppColors.textPrimary),
            onPressed: () async {
              await Provider.of<AuthProvider>(context, listen: false).logout();
              if (mounted) {
                Navigator.of(context).pushAndRemoveUntil(
                  MaterialPageRoute(builder: (_) => const LoginScreen()),
                  (route) => false,
                );
              }
            },
          ),
        ],
      ),
      body: _buildBody(firstName),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _selectedIndex,
        onDestinationSelected: (index) =>
            setState(() => _selectedIndex = index),
        backgroundColor: AppColors.surface,
        indicatorColor: AppColors.primaryLighter,
        destinations: [
          NavigationDestination(
            icon: Icon(Icons.dashboard_outlined),
            selectedIcon: Icon(Icons.dashboard, color: AppColors.primary),
            label: 'Home',
          ),
          NavigationDestination(
            icon: Icon(Icons.analytics_outlined),
            selectedIcon: Icon(Icons.analytics, color: AppColors.primary),
            label: 'Analytics',
          ),
          NavigationDestination(
            icon: Icon(Icons.person_outline),
            selectedIcon: Icon(Icons.person, color: AppColors.primary),
            label: 'Profile',
          ),
        ],
      ),
    );
  }

  Widget _buildBody(String name) {
    if (_isLoading) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_error != null) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.error_outline, size: 48, color: AppColors.error),
            const SizedBox(height: 16),
            Text(
              'Error loading dashboard',
              style: TextStyle(color: AppColors.textSecondary),
            ),
            TextButton(onPressed: _loadDashboard, child: const Text('Retry')),
          ],
        ),
      );
    }

    switch (_selectedIndex) {
      case 0:
        return _buildHomeTab(name);
      case 1:
        return _buildAnalyticsTab();
      case 2:
        return _buildProfileTab();
      default:
        return _buildHomeTab(name);
    }
  }

  String _getVitalValue(String key) {
    if (_data == null) return '--';

    // Key mapping
    final mappedKey = key.toLowerCase();

    final summary =
        _data!.vitalsSummary[mappedKey] ??
        _data!.vitalsSummary[key.toUpperCase()] ??
        _data!.vitalsSummary[key];

    if (summary == null) return '--';

    // Formatting logic based on structure
    // We prefer latest reading, but fallback to average
    if (summary.latestReading != null) {
      final latest = summary.latestReading!;
      if (latest['values'] != null && latest['values'] is Map) {
        final vals = latest['values'];
        final sys = vals['systolic'] ?? '--';
        final dia = vals['diastolic'] ?? '--';
        return '$sys/$dia';
      } else if (latest['value'] != null) {
        return latest['value'].toString();
      }
    }

    return summary.average?.toStringAsFixed(1) ?? '--';
  }

  Widget _buildHomeTab(String name) {
    if (_data == null) return const SizedBox();

    return RefreshIndicator(
      onRefresh: _loadDashboard,
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        physics: const AlwaysScrollableScrollPhysics(),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Greeting
            Text(
              'Hello, $name 👋',
              style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                color: AppColors.textPrimary,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              'How are you feeling today?',
              style: Theme.of(
                context,
              ).textTheme.bodyLarge?.copyWith(color: AppColors.textSecondary),
            ),
            const SizedBox(height: 24),

            // Health Score Card
            Container(
              padding: const EdgeInsets.all(28),
              decoration: BoxDecoration(
                gradient: AppColors.primaryGradient,
                borderRadius: BorderRadius.circular(32),
                boxShadow: [
                  BoxShadow(
                    color: AppColors.primary.withOpacity(0.3),
                    blurRadius: 20,
                    offset: const Offset(0, 10),
                  ),
                ],
              ),
              child: Column(
                children: [
                  Text(
                    'Health Score',
                    style: TextStyle(
                      color: Colors.white.withOpacity(0.9),
                      fontSize: 16,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                  const SizedBox(height: 16),
                  // Health Score display
                  Text(
                    '${_data!.healthScore.score}',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 64,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 12),
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 16,
                      vertical: 8,
                    ),
                    decoration: BoxDecoration(
                      color: Colors.white.withOpacity(0.2),
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.trending_up, color: Colors.white, size: 18),
                        const SizedBox(width: 6),
                        Text(
                          _data!.healthScore.category,
                          style: TextStyle(
                            color: Colors.white,
                            fontSize: 14,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),

            const SizedBox(height: 24),

            // Vitals Grid
            GridView.count(
              crossAxisCount: 2,
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              mainAxisSpacing: 16,
              crossAxisSpacing: 16,
              childAspectRatio: 1.1,
              children: [
                _buildVitalCard(
                  title: 'Blood Pressure',
                  value: _getVitalValue('bp'),
                  unit: 'mmHg',
                  icon: FontAwesomeIcons.heartPulse,
                  color: AppColors.vitalsRed,
                  vitalCode: 'BP',
                ),
                _buildVitalCard(
                  title: 'Heart Rate',
                  value: _getVitalValue('hr'),
                  unit: 'bpm',
                  icon: FontAwesomeIcons.heartbeat,
                  color: AppColors.vitalsPink,
                  vitalCode: 'HR',
                ),
                _buildVitalCard(
                  title: 'Oxygen',
                  value: _getVitalValue('spo2'),
                  unit: '%',
                  icon: FontAwesomeIcons.lungs,
                  color: AppColors.vitalsBlue,
                  vitalCode: 'SPO2',
                ),
                _buildVitalCard(
                  title: 'Temperature',
                  value: _getVitalValue('temp'),
                  unit: '°F',
                  icon: FontAwesomeIcons.temperatureHalf,
                  color: AppColors.vitalsOrange,
                  vitalCode: 'TEMP',
                ),
              ],
            ),

            const SizedBox(height: 24),

            // Medications Section
            Container(
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(
                color: AppColors.surface,
                borderRadius: BorderRadius.circular(32),
                border: Border.all(color: AppColors.primary.withOpacity(0.1)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // ... existing medication code ...
                  GestureDetector(
                    onTap: () {
                      Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (_) => const MedicationsScreen(),
                        ),
                      );
                    },
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(
                          'Today\'s Medications',
                          style: Theme.of(context).textTheme.titleLarge
                              ?.copyWith(
                                fontWeight: FontWeight.bold,
                                color: AppColors.textPrimary,
                              ),
                        ),
                        if (_data != null)
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
                                  '${_data!.medicationAdherence.rate.toInt()}%',
                                  style: TextStyle(
                                    color: AppColors.primary,
                                    fontSize: 14,
                                    fontWeight: FontWeight.bold,
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
                          )
                        else
                          Icon(
                            Icons.arrow_forward_ios,
                            size: 16,
                            color: AppColors.textTertiary,
                          ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 20),
                  if (_medications.isEmpty)
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 20),
                      child: Center(
                        child: Text(
                          'No medications scheduled',
                          style: TextStyle(color: AppColors.textSecondary),
                        ),
                      ),
                    )
                  else
                    ..._medications.map(
                      (med) => Column(
                        children: [
                          _buildMedItem(
                            med['id'],
                            med['name'] ?? 'Unknown',
                            med['dosage'] ?? '',
                            med['time'] ?? 'Today',
                            med['taken'] ?? false,
                          ),
                          const SizedBox(height: 12),
                          Divider(color: AppColors.divider, height: 1),
                          const SizedBox(height: 12),
                        ],
                      ),
                    ),
                ],
              ),
            ),

            const SizedBox(height: 24),

            // Family & Care Team
            GestureDetector(
              onTap: () {
                Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) => const FamilyMembersScreen(),
                  ),
                );
              },
              child: Container(
                padding: const EdgeInsets.all(24),
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    colors: [
                      AppColors.secondary,
                      AppColors.secondary.withOpacity(0.8),
                    ],
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                  ),
                  borderRadius: BorderRadius.circular(32),
                  boxShadow: [
                    BoxShadow(
                      color: AppColors.secondary.withOpacity(0.3),
                      blurRadius: 20,
                      offset: const Offset(0, 10),
                    ),
                  ],
                ),
                child: Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        color: Colors.white.withOpacity(0.2),
                        shape: BoxShape.circle,
                      ),
                      child: Icon(
                        Icons.family_restroom,
                        color: Colors.white,
                        size: 28,
                      ),
                    ),
                    const SizedBox(width: 20),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Family & Care Team',
                            style: TextStyle(
                              fontSize: 18,
                              fontWeight: FontWeight.bold,
                              color: Colors.white,
                            ),
                          ),
                          const SizedBox(height: 4),
                          Text(
                            'Manage access and members',
                            style: TextStyle(
                              fontSize: 14,
                              color: Colors.white.withOpacity(0.8),
                            ),
                          ),
                        ],
                      ),
                    ),
                    Icon(
                      Icons.arrow_forward_ios,
                      color: Colors.white,
                      size: 20,
                    ),
                  ],
                ),
              ),
            ),

            const SizedBox(height: 24),
          ],
        ),
      ),
    );
  }

  Widget _buildAnalyticsTab() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.analytics_outlined,
            size: 80,
            color: AppColors.primary.withOpacity(0.3),
          ),
          const SizedBox(height: 16),
          Text(
            'Analytics Coming Soon',
            style: Theme.of(
              context,
            ).textTheme.titleLarge?.copyWith(color: AppColors.textSecondary),
          ),
        ],
      ),
    );
  }

  Widget _buildProfileTab() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.person_outline,
            size: 80,
            color: AppColors.primary.withOpacity(0.3),
          ),
          const SizedBox(height: 16),
          Text(
            'Profile Coming Soon',
            style: Theme.of(
              context,
            ).textTheme.titleLarge?.copyWith(color: AppColors.textSecondary),
          ),
        ],
      ),
    );
  }

  Widget _buildVitalCard({
    required String title,
    required String value,
    required String unit,
    required IconData icon,
    required Color color,
    required String vitalCode,
  }) {
    return GestureDetector(
      onTap: () {
        Navigator.push(
          context,
          MaterialPageRoute(
            builder: (_) => VitalsDetailScreen(
              vitalCode: vitalCode,
              vitalName: title,
              color: color,
              icon: icon,
            ),
          ),
        );
      },
      child: Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(24),
          border: Border.all(color: color.withOpacity(0.2), width: 1.5),
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
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
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
                  child: Icon(icon, color: color, size: 20),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 10,
                    vertical: 4,
                  ),
                  decoration: BoxDecoration(
                    color: AppColors.success.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    'Normal',
                    style: TextStyle(
                      color: AppColors.success,
                      fontSize: 11,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              ],
            ),
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: TextStyle(
                    fontSize: 13,
                    color: AppColors.textSecondary,
                    fontWeight: FontWeight.w500,
                  ),
                ),
                const SizedBox(height: 6),
                Row(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Text(
                      value,
                      style: TextStyle(
                        fontSize: 24,
                        fontWeight: FontWeight.bold,
                        color: AppColors.textPrimary,
                      ),
                    ),
                    const SizedBox(width: 4),
                    Padding(
                      padding: const EdgeInsets.only(bottom: 3),
                      child: Text(
                        unit,
                        style: TextStyle(
                          fontSize: 12,
                          color: AppColors.textSecondary,
                        ),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildMedItem(
    int? id,
    String name,
    String dosage,
    String status,
    bool isTaken,
  ) {
    return Row(
      children: [
        Container(
          width: 56,
          height: 56,
          decoration: BoxDecoration(
            color: isTaken
                ? AppColors.success.withOpacity(0.1)
                : AppColors.alert.withOpacity(0.1),
            borderRadius: BorderRadius.circular(16),
          ),
          child: Icon(
            isTaken ? Icons.check_circle : Icons.schedule,
            color: isTaken ? AppColors.success : AppColors.alert,
            size: 28,
          ),
        ),
        const SizedBox(width: 16),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                name,
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                  color: AppColors.textPrimary,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                '$dosage • $status',
                style: TextStyle(fontSize: 14, color: AppColors.textSecondary),
              ),
            ],
          ),
        ),
        if (!isTaken)
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: AppColors.success.withOpacity(0.1),
              borderRadius: BorderRadius.circular(12),
            ),
            child: IconButton(
              icon: Icon(Icons.check, color: AppColors.success, size: 20),
              padding: EdgeInsets.zero,
              onPressed: () {
                if (id != null) {
                  _markAsTaken(id);
                }
              },
            ),
          ),
      ],
    );
  }
}
