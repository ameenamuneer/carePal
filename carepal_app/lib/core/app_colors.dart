import 'package:flutter/material.dart';

class AppColors {
  // Core Authority (#0D9488)
  static const Color primary = Color(0xFF0D9488);
  static const Color primaryDark = Color(0xFF115E59);
  static const Color primaryLight = Color(0xFF2DD4BF);
  static const Color primaryLighter = Color(0xFFCCFBF1);

  // Serene Surface
  static const Color background = Color(0xFFF0FDFA);
  static const Color backgroundDark = Color(
    0xFFCCFBF1,
  ); // Using primaryLighter as similar to background but distinct if needed, or just a darker shade. Let's use a neutralized version.
  // Actually, backgroundDark is used for disabled chip color.

  static const Color surface = Color(0xFFFFFFFF);

  static const Color info = Color(0xFF3B82F6); // Blue for info

  // Vital Alert
  static const Color alert = Color(0xFFF97316);
  static const Color warning = Color(0xFFFBBF24);
  static const Color error = Color(0xFFEF4444);
  static const Color success = Color(0xFF10B981);

  // Text
  static const Color textPrimary = Color(0xFF115E59);
  static const Color textSecondary = Color(0xFF64748B);
  static const Color textTertiary = Color(0xFF94A3B8);

  // Vitals
  static const Color vitalsRed = Color(0xFFDC2626);
  static const Color vitalsPink = Color(0xFFEC4899);
  static const Color vitalsBlue = Color(0xFF3B82F6);
  static const Color vitalsOrange = Color(0xFFF97316);
  static const Color vitalsPurple = Color(0xFF8B5CF6);
  static const Color vitalsGreen = Color(0xFF10B981);

  // Utility
  static const Color border = Color(0xFFE2E8F0);
  static const Color divider = Color(0xFFE2E8F0);
  static const Color shadowLight = Color(0x0F000000);
  static const Color errorLight = Color(0xFFFEE2E2);

  // Gradients
  static const LinearGradient primaryGradient = LinearGradient(
    colors: [Color(0xFF0D9488), Color(0xFF14B8A6)],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );
}
