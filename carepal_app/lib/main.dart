import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'providers/auth_provider.dart';
import 'screens/login_screen.dart';
import 'core/app_theme.dart';

void main() {
  runApp(
    MultiProvider(
      providers: [ChangeNotifierProvider(create: (_) => AuthProvider())],
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
          // Here you could add a Splash Screen if isLoading is true initially
          // For now, simpler flow:
          return const LoginScreen();
        },
      ),
    );
  }
}
