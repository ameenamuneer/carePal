import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'dart:async';
import 'services/api_service.dart';
import 'providers/auth_provider.dart';
import 'providers/dashboard_provider.dart';
import 'providers/vitals_provider.dart';
import 'providers/medication_provider.dart';
import 'providers/device_provider.dart';
import 'providers/family_provider.dart';
import 'providers/ai_agent_provider.dart';
import 'providers/profile_provider.dart'; // Import ProfileProvider
import 'providers/abdm_provider.dart'; // AbdmProvider
import 'services/ble_servo_service.dart';
import 'screens/login_screen.dart';
import 'screens/dashboard_screen.dart'; // Ensure DashboardScreen is imported for logic or home redirect
import 'core/app_theme.dart'; // Using existing AppTheme

void main() async {
  runZonedGuarded(
    () async {
      WidgetsFlutterBinding.ensureInitialized();
      print("🚀 [DEBUG] App Starting...");

      // Initialize API service
      try {
        final apiService = ApiService();
        apiService.initialize();
        print("✅ [DEBUG] ApiService Initialized");

        await apiService.loadTokens();
        print("✅ [DEBUG] Tokens Loaded");
      } catch (e, stack) {
        print("❌ [DEBUG] API Init Failed: $e\n$stack");
      }

      print("🚀 [DEBUG] Calling runApp...");
      runApp(
        MultiProvider(
          providers: [
            ChangeNotifierProvider(
              create: (_) {
                print("📦 [DEBUG] Init AuthProvider");
                return AuthProvider();
              },
            ),
            ChangeNotifierProvider(create: (_) => DashboardProvider()),
            ChangeNotifierProvider(create: (_) => VitalsProvider()),
            ChangeNotifierProvider(create: (_) => MedicationProvider()),
            ChangeNotifierProvider(create: (_) => DeviceProvider()),
            ChangeNotifierProvider(create: (_) => FamilyProvider()),
            ChangeNotifierProvider(create: (_) => AIAgentProvider()),
            ChangeNotifierProvider(create: (_) => ProfileProvider()),
            ChangeNotifierProvider(create: (_) => AbdmProvider()),
            ChangeNotifierProvider(
              create: (_) {
                print("📦 [DEBUG] Init BleServoService");
                return BleServoService();
              },
            ),
          ],
          child: const CarePalApp(),
        ),
      );
    },
    (error, stack) {
      print("🔥 [CRITICAL] Uncaught Error in main: $error\n$stack");
    },
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
