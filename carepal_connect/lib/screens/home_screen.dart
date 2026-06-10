import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';
import '../core/app_colors.dart';
import '../providers/auth_provider.dart';
import '../providers/patient_provider.dart';
import '../providers/activity_log_provider.dart';
import 'dashboard_screen.dart';
import 'activity_log_screen.dart';
import 'patients_screen.dart';
import 'link_patient_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int _currentIndex = 0;

  final List<Widget> _screens = const [
    DashboardScreen(),
    ActivityLogScreen(),
    PatientsScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    final patientProvider = context.watch<PatientProvider>();
    final authProvider = context.watch<AuthProvider>();

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: AppColors.surface,
        elevation: 0,
        title: Text(
          'CarePal Connect',
          style: GoogleFonts.lexend(
            fontSize: 20,
            fontWeight: FontWeight.bold,
            color: AppColors.primaryDark,
          ),
        ),
        actions: [
          // Account type badge
          Container(
            margin: const EdgeInsets.only(right: 12),
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
            decoration: BoxDecoration(
              color: authProvider.isDoctor
                  ? AppColors.vitalsBlue.withOpacity(0.12)
                  : AppColors.primaryLighter,
              borderRadius: BorderRadius.circular(20),
            ),
            child: Text(
              authProvider.isDoctor ? 'DOCTOR' : 'FAMILY',
              style: GoogleFonts.lexend(
                fontSize: 11,
                fontWeight: FontWeight.w700,
                color: authProvider.isDoctor
                    ? AppColors.vitalsBlue
                    : AppColors.primary,
              ),
            ),
          ),
          PopupMenuButton<String>(
            icon: const Icon(Icons.more_vert, color: AppColors.textSecondary),
            onSelected: (value) async {
              if (value == 'logout') {
                await context.read<AuthProvider>().logout();
                if (mounted) {
                  Navigator.of(context).pushNamedAndRemoveUntil('/', (_) => false);
                }
              }
            },
            itemBuilder: (_) => [
              const PopupMenuItem(value: 'logout', child: Text('Logout')),
            ],
          ),
        ],
      ),
      body: Column(
        children: [
          // Patient switcher bar
          _PatientSwitcherBar(
            patientProvider: patientProvider,
          ),
          const Divider(height: 1),
          Expanded(
            child: patientProvider.isLoading
                ? const Center(
                    child: CircularProgressIndicator(color: AppColors.primary))
                : _screens[_currentIndex],
          ),
        ],
      ),
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _currentIndex,
        onTap: (i) => setState(() => _currentIndex = i),
        items: const [
          BottomNavigationBarItem(
            icon: Icon(Icons.home_outlined),
            activeIcon: Icon(Icons.home),
            label: 'Dashboard',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.history_outlined),
            activeIcon: Icon(Icons.history),
            label: 'Activity Log',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.people_outline),
            activeIcon: Icon(Icons.people),
            label: 'Patients',
          ),
        ],
      ),
    );
  }
}

class _PatientSwitcherBar extends StatelessWidget {
  final PatientProvider patientProvider;

  const _PatientSwitcherBar({required this.patientProvider});

  @override
  Widget build(BuildContext context) {
    final patients = _buildPatientList(patientProvider);

    if (patients.isEmpty) {
      return Container(
        color: AppColors.surface,
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        child: Row(
          children: [
            Icon(Icons.info_outline,
                size: 16, color: AppColors.textSecondary),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                'No patients linked yet',
                style: TextStyle(
                    fontSize: 13, color: AppColors.textSecondary),
              ),
            ),
            TextButton.icon(
              onPressed: () => Navigator.of(context).push(
                MaterialPageRoute(builder: (_) => const LinkPatientScreen()),
              ),
              icon: const Icon(Icons.add, size: 16),
              label: const Text('Link Patient'),
              style: TextButton.styleFrom(
                foregroundColor: AppColors.primary,
                padding:
                    const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                textStyle: const TextStyle(
                    fontSize: 13, fontWeight: FontWeight.w600),
              ),
            ),
          ],
        ),
      );
    }

    return Container(
      color: AppColors.surface,
      height: 56,
      child: ListView.builder(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        itemCount: patients.length + 1, // +1 for "+" chip
        itemBuilder: (context, index) {
          if (index == patients.length) {
            // "+" chip at end
            return GestureDetector(
              onTap: () => Navigator.of(context).push(
                MaterialPageRoute(builder: (_) => const LinkPatientScreen()),
              ),
              child: Container(
                margin: const EdgeInsets.only(left: 6),
                padding: const EdgeInsets.symmetric(horizontal: 14),
                decoration: BoxDecoration(
                  color: AppColors.background,
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(color: AppColors.border),
                ),
                child: const Icon(Icons.add,
                    size: 18, color: AppColors.textSecondary),
              ),
            );
          }

          final p = patients[index];
          final isActive = patientProvider.activePatientId == p.id;
          final initials = _initials(p.name);

          return GestureDetector(
            onTap: () {
              patientProvider.setActivePatient(p.id, p.name);
              context
                  .read<ActivityLogProvider>()
                  .setPatientAndReload(p.id);
            },
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 200),
              margin: const EdgeInsets.only(right: 8),
              padding: const EdgeInsets.symmetric(horizontal: 12),
              decoration: BoxDecoration(
                color: isActive ? AppColors.primary : AppColors.background,
                borderRadius: BorderRadius.circular(20),
                border: Border.all(
                  color: isActive ? AppColors.primary : AppColors.border,
                ),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  CircleAvatar(
                    radius: 12,
                    backgroundColor: isActive
                        ? Colors.white.withOpacity(0.2)
                        : AppColors.primaryLighter,
                    child: Text(
                      initials,
                      style: TextStyle(
                        fontSize: 10,
                        fontWeight: FontWeight.bold,
                        color: isActive ? Colors.white : AppColors.primary,
                      ),
                    ),
                  ),
                  const SizedBox(width: 6),
                  Text(
                    p.name,
                    style: GoogleFonts.lexend(
                      fontSize: 13,
                      fontWeight: FontWeight.w500,
                      color:
                          isActive ? Colors.white : AppColors.textPrimary,
                    ),
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }

  List<_PatientItem> _buildPatientList(PatientProvider provider) {
    final result = <_PatientItem>[];
    for (final link in provider.clinicalLinks) {
      result.add(_PatientItem(id: link.patient, name: link.patientName));
    }
    for (final link in provider.familyLinks) {
      result.add(_PatientItem(id: link.patient, name: link.patientName));
    }
    return result;
  }

  String _initials(String name) {
    final parts = name.trim().split(' ');
    if (parts.isEmpty) return '?';
    if (parts.length == 1) return parts[0][0].toUpperCase();
    return '${parts[0][0]}${parts[1][0]}'.toUpperCase();
  }
}

class _PatientItem {
  final int id;
  final String name;
  _PatientItem({required this.id, required this.name});
}
