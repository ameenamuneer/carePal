import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'dart:async';
import 'services/api_service.dart';
import 'providers/auth_provider.dart';
import 'providers/patient_provider.dart';
import 'providers/activity_log_provider.dart';
import 'providers/medication_provider.dart';
import 'providers/dashboard_provider.dart';
import 'screens/login_screen.dart';
import 'screens/home_screen.dart';
import 'core/app_theme.dart';

void main() async {
  runZonedGuarded(
    () async {
      WidgetsFlutterBinding.ensureInitialized();

      try {
        final apiService = ApiService();
        apiService.initialize();
        await apiService.loadTokens();
      } catch (e) {
        print('API Init error: $e');
      }

      final authProvider = AuthProvider();
      final patientProvider = PatientProvider();
      final activityLogProvider = ActivityLogProvider();
      final medicationProvider = MedicationProvider();
      final dashboardProvider = DashboardProvider();

      // Bind sibling providers so AuthProvider can clear them on session change.
      authProvider.bindDependentProviders(
          patientProvider, activityLogProvider, medicationProvider,
          dashboardProvider: dashboardProvider);

      runApp(
        MultiProvider(
          providers: [
            ChangeNotifierProvider.value(value: authProvider),
            ChangeNotifierProvider.value(value: patientProvider),
            ChangeNotifierProvider.value(value: activityLogProvider),
            ChangeNotifierProvider.value(value: medicationProvider),
            ChangeNotifierProvider.value(value: dashboardProvider),
          ],
          child: const CarePalConnectApp(),
        ),
      );
    },
    (error, stack) {
      print('Uncaught error: $error\n$stack');
    },
  );
}

class CarePalConnectApp extends StatelessWidget {
  const CarePalConnectApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'CarePal Connect',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.lightTheme,
      home: const _AuthGate(),
    );
  }
}

class _AuthGate extends StatefulWidget {
  const _AuthGate();

  @override
  State<_AuthGate> createState() => _AuthGateState();
}

class _AuthGateState extends State<_AuthGate> {
  bool _checked = false;

  @override
  void initState() {
    super.initState();
    _checkAuth();
  }

  Future<void> _checkAuth() async {
    final authProvider = context.read<AuthProvider>();
    await authProvider.checkAuthStatus();

    if (authProvider.isAuthenticated) {
      final userType = authProvider.userType;
      // Only allow DOCTOR or FAMILY accounts
      if (userType == 'DOCTOR' || userType == 'FAMILY') {
        final patientProv = context.read<PatientProvider>();
        await patientProv.loadLinks(userType);
        // Pre-load medications for the initially active patient
        if (patientProv.activePatientId != null) {
          context
              .read<MedicationProvider>()
              .setPatientAndReload(patientProv.activePatientId);
        }
      } else {
        // Wrong account type — force logout
        await authProvider.logout();
      }
    }

    if (mounted) {
      setState(() => _checked = true);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (!_checked) {
      return const Scaffold(
        backgroundColor: Color(0xFF0D9488),
        body: Center(
          child: CircularProgressIndicator(color: Colors.white),
        ),
      );
    }

    final auth = context.watch<AuthProvider>();
    if (auth.isAuthenticated &&
        (auth.userType == 'DOCTOR' || auth.userType == 'FAMILY')) {
      return const HomeScreen();
    }
    return const LoginScreen();
  }
}
