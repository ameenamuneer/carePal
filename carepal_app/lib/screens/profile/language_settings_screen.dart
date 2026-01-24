// lib/screens/profile/language_settings_screen.dart
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../core/app_colors.dart';
import '../../providers/profile_provider.dart';

class LanguageSettingsScreen extends StatefulWidget {
  const LanguageSettingsScreen({super.key});

  @override
  State<LanguageSettingsScreen> createState() => _LanguageSettingsScreenState();
}

class _LanguageSettingsScreenState extends State<LanguageSettingsScreen> {
  final List<Map<String, String>> _supportedLanguages = [
    {'code': 'en', 'name': 'English', 'nativeName': 'English'},
    {'code': 'hi', 'name': 'Hindi', 'nativeName': 'हिन्दी'},
    {'code': 'ta', 'name': 'Tamil', 'nativeName': 'தமிழ்'},
    {'code': 'te', 'name': 'Telugu', 'nativeName': 'తెలుగు'},
    {'code': 'kn', 'name': 'Kannada', 'nativeName': 'ಕನ್ನಡ'},
    {'code': 'ml', 'name': 'Malayalam', 'nativeName': 'മലയാളം'},
    {'code': 'mr', 'name': 'Marathi', 'nativeName': 'मराठी'},
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.surface, // surfaceMint -> surface
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(
            Icons.arrow_back,
            color: AppColors.textPrimary,
          ), // deepTeal -> textPrimary
          onPressed: () => Navigator.pop(context),
        ),
        title: const Text(
          'Language',
          style: TextStyle(
            color: AppColors.textPrimary,
            fontWeight: FontWeight.bold,
          ),
        ),
      ),
      body: Consumer<ProfileProvider>(
        builder: (context, profileProvider, _) {
          final currentLanguage = profileProvider.preferredLanguage
              .toLowerCase();

          return ListView(
            padding: const EdgeInsets.all(20),
            children: [
              Container(
                padding: const EdgeInsets.all(20),
                decoration: BoxDecoration(
                  gradient: AppColors.primaryGradient,
                  borderRadius: BorderRadius.circular(24),
                ),
                child: Column(
                  children: [
                    const Icon(Icons.language, size: 48, color: Colors.white),
                    const SizedBox(height: 12),
                    const Text(
                      'Voice & Text Language',
                      style: TextStyle(
                        fontSize: 20,
                        fontWeight: FontWeight.bold,
                        color: Colors.white,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'Choose your preferred language for the app and voice assistant',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        fontSize: 14,
                        color: Colors.white.withOpacity(
                          0.9,
                        ), // withValues -> withOpacity
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 24),
              Container(
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(20),
                  boxShadow: [
                    BoxShadow(
                      color: AppColors.primary.withOpacity(0.05),
                      blurRadius: 10,
                      offset: const Offset(0, 4),
                    ),
                  ],
                ),
                child: Column(
                  children: [
                    for (int i = 0; i < _supportedLanguages.length; i++) ...[
                      _buildLanguageTile(
                        language: _supportedLanguages[i],
                        isSelected: currentLanguage.startsWith(
                          _supportedLanguages[i]['code']!.toLowerCase(),
                        ),
                        onTap: () => _selectLanguage(
                          context,
                          _supportedLanguages[i]['code']!,
                          profileProvider,
                        ),
                      ),
                      if (i < _supportedLanguages.length - 1)
                        Divider(
                          height: 1,
                          indent: 68,
                          color: AppColors.primary.withOpacity(0.1),
                        ),
                    ],
                  ],
                ),
              ),
              const SizedBox(height: 20),
              Container(
                padding: const EdgeInsets.all(20),
                decoration: BoxDecoration(
                  color: Colors.blue.shade50,
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: Colors.blue.shade200),
                ),
                child: Row(
                  children: [
                    Icon(
                      Icons.info_outline,
                      color: Colors.blue.shade700,
                      size: 24,
                    ),
                    const SizedBox(width: 16),
                    Expanded(
                      child: Text(
                        'The AI voice assistant will speak in your selected language. Text messages will also be translated.',
                        style: TextStyle(
                          fontSize: 13,
                          color: Colors.blue.shade900,
                          height: 1.4,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          );
        },
      ),
    );
  }

  Widget _buildLanguageTile({
    required Map<String, String> language,
    required bool isSelected,
    required VoidCallback onTap,
  }) {
    return ListTile(
      onTap: onTap,
      contentPadding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
      leading: Container(
        width: 48,
        height: 48,
        decoration: BoxDecoration(
          gradient: isSelected
              ? AppColors.primaryGradient
              : LinearGradient(
                  colors: [Colors.grey.shade200, Colors.grey.shade300],
                ),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Center(
          child: Text(
            language['code']!.toUpperCase(),
            style: TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.bold,
              color: isSelected ? Colors.white : Colors.grey.shade700,
            ),
          ),
        ),
      ),
      title: Text(
        language['name']!,
        style: TextStyle(
          fontSize: 16,
          fontWeight: FontWeight.w600,
          color: isSelected
              ? AppColors.primary
              : AppColors.textPrimary, // deepTeal -> textPrimary
        ),
      ),
      subtitle: Text(
        language['nativeName']!,
        style: TextStyle(
          fontSize: 14,
          color: AppColors.textPrimary.withOpacity(
            0.6,
          ), // deepTeal -> textPrimary
        ),
      ),
      trailing: isSelected
          ? const Icon(Icons.check_circle, color: AppColors.primary, size: 24)
          : Icon(Icons.circle_outlined, color: Colors.grey.shade400, size: 24),
    );
  }

  Future<void> _selectLanguage(
    BuildContext context,
    String languageCode,
    ProfileProvider profileProvider,
  ) async {
    if (profileProvider.patientId == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Unable to update language preference'),
          backgroundColor: Colors.red,
        ),
      );
      return;
    }

    final success = await profileProvider.updatePatientProfile({
      'preferred_language': languageCode.toUpperCase(),
    });

    if (success && context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Row(
            children: [
              const Icon(Icons.check_circle, color: Colors.white),
              const SizedBox(width: 12),
              Text('Language updated to ${_getLanguageName(languageCode)}'),
            ],
          ),
          backgroundColor: AppColors.primary,
          behavior: SnackBarBehavior.floating,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
        ),
      );
    }
  }

  String _getLanguageName(String code) {
    final language = _supportedLanguages.firstWhere(
      (lang) => lang['code'] == code,
      orElse: () => {'name': code},
    );
    return language['name']!;
  }
}
