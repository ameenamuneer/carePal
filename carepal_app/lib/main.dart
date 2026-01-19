import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'services/api_service.dart';
import 'providers/auth_provider.dart';
import 'providers/dashboard_provider.dart';
import 'providers/vitals_provider.dart';
import 'providers/medication_provider.dart';
import 'providers/device_provider.dart';
import 'providers/family_provider.dart';
import 'providers/ai_agent_provider.dart';
import 'screens/login_screen.dart';
import 'screens/dashboard_screen.dart'; // Ensure DashboardScreen is imported for logic or home redirect
import 'core/app_theme.dart'; // Using existing AppTheme

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Initialize API service
  final apiService = ApiService();
  apiService.initialize();
  await apiService.loadTokens();

  runApp(
    MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => AuthProvider()),
        ChangeNotifierProvider(create: (_) => DashboardProvider()),
        ChangeNotifierProvider(create: (_) => VitalsProvider()),
        ChangeNotifierProvider(create: (_) => MedicationProvider()),
        ChangeNotifierProvider(create: (_) => DeviceProvider()),
        ChangeNotifierProvider(create: (_) => FamilyProvider()),
        ChangeNotifierProvider(create: (_) => AIAgentProvider()),
      ],
      child: const CarePalApp(),
    ),
  );
}

class CarePalApp extends StatelessWidget {
  const CarePalApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'CarePAL',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.lightTheme,
      home: Consumer<AuthProvider>(
        builder: (context, auth, _) {
          return auth.isAuthenticated
              ? const DashboardScreen()
              : const LoginScreen();
        },
      ),
    );
  }
}
