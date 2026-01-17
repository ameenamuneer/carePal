import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'providers/auth_provider.dart';
import 'screens/login_screen.dart';

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
      theme: ThemeData(primarySwatch: Colors.blue),
      home: const LoginScreen(),
    );
  }
}
