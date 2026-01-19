import 'package:flutter/material.dart';

class AppColors {
  AppColors._();

  // Primary Brand Colors - CarePAL Teal/Mint
  static const Color primary = Color(0xFF0D9488);
  static const Color primaryDark = Color(0xFF115E59);
  static const Color primaryLight = Color(0xFF2DD4BF);
  static const Color primaryLighter = Color(0xFFF0FDFA);
  static const Color secondary = Color(0xFF6366F1); // Indigo

  // Alert & Status Colors
  static const Color alert = Color(0xFFF97316);
  static const Color alertLight = Color(0xFFFED7AA);
  static const Color success = Color(0xFF10B981);
  static const Color successLight = Color(0xFFD1FAE5);
  static const Color warning = Color(0xFFFBBF24);
  static const Color warningLight = Color(0xFFFEF3C7);
  static const Color error = Color(0xFFEF4444);
  static const Color errorLight = Color(0xFFFEE2E2);
  static const Color info = Color(0xFF3B82F6);
  static const Color infoLight = Color(0xFFDBEAFE);

  // Vital-Specific Colors
  static const Color vitalsRed = Color(0xFFDC2626); // Blood Pressure
  static const Color vitalsPink = Color(0xFFEC4899); // Heart Rate
  static const Color vitalsBlue = Color(0xFF3B82F6); // Oxygen
  static const Color vitalsOrange = Color(0xFFF97316); // Temperature
  static const Color vitalsGreen = Color(0xFF10B981); // General Health
  static const Color vitalsPurple = Color(0xFF8B5CF6); // Glucose

  // Neutral Colors
  static const Color background = Color(0xFFF0FDFA);
  static const Color backgroundDark = Color(0xFFCCFBF1);
  static const Color surface = Color(0xFFFFFFFF);
  static const Color surfaceVariant = Color(0xFFFAFAFA);

  // Text Colors
  static const Color textPrimary = Color(0xFF115E59);
  static const Color textSecondary = Color(0xFF0F766E);
  static const Color textTertiary = Color(0xFF14B8A6);
  static const Color textLight = Color(0xFFFFFFFF);
  static const Color textDisabled = Color(0xFF94A3B8);

  // Divider & Border
  static const Color divider = Color(0xFF99F6E4);
  static const Color border = Color(0xFF5EEAD4);
  static const Color borderLight = Color(0xFFCCFBF1);

  // Gradients
  static const LinearGradient primaryGradient = LinearGradient(
    colors: [Color(0xFF0D9488), Color(0xFF115E59)],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );

  static const LinearGradient accentGradient = LinearGradient(
    colors: [Color(0xFF2DD4BF), Color(0xFF0D9488)],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );

  // Shadows
  static Color shadowLight = Colors.black.withOpacity(0.05);
  static Color shadowMedium = Colors.black.withOpacity(0.1);
  static Color shadowDark = Colors.black.withOpacity(0.15);

  // Helper Methods
  static Color getVitalColor(String vitalCode) {
    switch (vitalCode.toUpperCase()) {
      case 'BP':
        return vitalsRed;
      case 'HR':
        return vitalsPink;
      case 'SPO2':
      case 'OXYGEN':
        return vitalsBlue;
      case 'TEMP':
      case 'TEMPERATURE':
        return vitalsOrange;
      case 'GLUCOSE':
        return vitalsPurple;
      default:
        return vitalsGreen;
    }
  }

  static Color getHealthScoreColor(int score) {
    if (score >= 80) return success;
    if (score >= 60) return primaryLight;
    if (score >= 40) return warning;
    return error;
  }
}
