import 'package:flutter/material.dart';

class AppColors {
  // Primary Utilities
  static const Color primary = Color(0xFF0D47A1); // Deep Medical Blue
  static const Color primaryLight = Color(0xFF5472D3);
  static const Color primaryDark = Color(0xFF002171);

  // Secondary / Accent
  static const Color accent = Color(0xFF00BFA5); // Medical Teal
  static const Color accentLight = Color(0xFF5DF2D6);
  static const Color accentDark = Color(0xFF008E76);

  // Backgrounds
  static const Color background = Color(0xFFF5F7FA); // Soft Grey-White
  static const Color surface = Colors.white;
  static const Color cardGradientStart = Color(0xFFFFFFFF);
  static const Color cardGradientEnd = Color(0xFFF0F4F8);

  // Text
  static const Color textPrimary = Color(0xFF1E293B); // Dark Slate
  static const Color textSecondary = Color(0xFF64748B); // Cool Grey
  static const Color textInverse = Colors.white;

  // Status
  static const Color success = Color(0xFF2ECC71);
  static const Color warning = Color(0xFFF1C40F);
  static const Color error = Color(0xFFE74C3C);
  static const Color info = Color(0xFF3498DB);

  // Custom Gradients
  static const LinearGradient primaryGradient = LinearGradient(
    colors: [Color(0xFF0D47A1), Color(0xFF1976D2)],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );

  static const LinearGradient glassGradient = LinearGradient(
    colors: [Colors.white70, Colors.white30],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );
}
