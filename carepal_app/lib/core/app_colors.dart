import 'package:flutter/material.dart';

class AppColors {
  // Core Authority (#0D9488) - Primary brand teal
  static const Color primary = Color(0xFF0D9488);

  // Deep Comfort (#115E59) - Contrast text / Primary Dark
  static const Color primaryDark = Color(0xFF115E59);
  static const Color textPrimary = Color(0xFF115E59);

  // Healing Mint (#2DD4BF) - Success / Primary Light
  static const Color primaryLight = Color(0xFF2DD4BF);
  static const Color success = Color(0xFF2DD4BF);

  // Serene Surface (#F0FDFA) - Background tint
  static const Color background = Color(0xFFF0FDFA);
  static const Color primaryLighter = Color(
    0xFFE0F2F1,
  ); // Slightly darker than background for contrast if needed

  // Vital Alert (#F97316) - Accent orange
  static const Color alert = Color(0xFFF97316);
  static const Color warning = Color(
    0xFFF97316,
  ); // Using orange for warning/alert

  // Standard colors
  static const Color surface = Color(0xFFFFFFFF);
  static const Color error = Color(
    0xFFEF4444,
  ); // Keep standard red for critical errors if needed, or use orange
  static const Color info = Color(0xFF0D9488); // Use primary for info

  // Text
  static const Color textSecondary = Color(0xFF64748B); // Slate 500
  static const Color textTertiary = Color(0xFF94A3B8); // Slate 400

  // Vitals Colors - Updating to match the new theme's aesthetic (or keep existing if not specified, but let's align)
  static const Color vitalsRed = Color(0xFFEF4444);
  static const Color vitalsPink = Color(0xFFEC4899);
  static const Color vitalsBlue = Color(0xFF3B82F6);
  static const Color vitalsOrange = Color(0xFFF97316);
  static const Color vitalsPurple = Color(0xFF8B5CF6);
  static const Color vitalsGreen = Color(0xFF10B981);

  // Utility
  static const Color border = Color(0xFFCCFBF1); // Teal 100 approx for borders
  static const Color divider = Color(0xFFE2E8F0);
  static const Color shadowLight = Color(0x0F0D9488); // Teal shadow
  static const Color errorLight = Color(0xFFFFEDD5); // Orange light

  // Gradients
  static const LinearGradient primaryGradient = LinearGradient(
    colors: [Color(0xFF0D9488), Color(0xFF115E59)],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );
}
