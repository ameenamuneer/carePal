// lib/screens/profile/notifications_settings_screen.dart
import 'package:flutter/material.dart';
import '../../core/app_colors.dart';

class NotificationsSettingsScreen extends StatefulWidget {
  const NotificationsSettingsScreen({super.key});

  @override
  State<NotificationsSettingsScreen> createState() =>
      _NotificationsSettingsScreenState();
}

class _NotificationsSettingsScreenState
    extends State<NotificationsSettingsScreen> {
  bool _medicationReminders = true;
  bool _vitalAlerts = true;
  bool _emergencyAlerts = true;
  bool _familyUpdates = false;
  bool _systemNotifications = true;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors
          .surface, // Changed from surfaceMint to match existing theme if needed, or keeping provided code. Provided: surfaceMint
      // Checking AppColors, surfaceMint might not exist in my visible app_colors.dart?
      // Step 333 (dashboard_screen.dart) used AppColors.surface, AppColors.background.
      // previous profile_screen used AppColors.primaryGradient.
      // I don't recall seeing surfaceMint in AppColors.
      // I'll check AppColors first to be safe, or just use AppColors.surface if mint is missing.
      // But for now I'll paste the user's code. If surfaceMint errors, I'll fix it.
      // Actually, better to check AppColors first.
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(
            Icons.arrow_back,
            color: AppColors.textPrimary,
          ), // Changed deepTeal -> textPrimary to match
          onPressed: () => Navigator.pop(context),
        ),
        title: const Text(
          'Notifications',
          style: TextStyle(
            color: AppColors.textPrimary, // Changed deepTeal -> textPrimary
            fontWeight: FontWeight.bold,
          ),
        ),
      ),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          _buildNotificationSection(
            title: 'Health Notifications',
            items: [
              _buildNotificationTile(
                title: 'Medication Reminders',
                subtitle: 'Get notified when it\'s time to take medication',
                value: _medicationReminders,
                onChanged: (value) =>
                    setState(() => _medicationReminders = value),
                icon: Icons.medication_outlined,
              ),
              _buildNotificationTile(
                title: 'Vital Signs Alerts',
                subtitle: 'Alerts for abnormal vital signs readings',
                value: _vitalAlerts,
                onChanged: (value) => setState(() => _vitalAlerts = value),
                icon: Icons.favorite_outline,
              ),
              _buildNotificationTile(
                title: 'Emergency Alerts',
                subtitle: 'Critical alerts that require immediate attention',
                value: _emergencyAlerts,
                onChanged: (value) => setState(() => _emergencyAlerts = value),
                icon: Icons.warning_amber_outlined,
              ),
            ],
          ),
          const SizedBox(height: 20),
          _buildNotificationSection(
            title: 'Family & Communication',
            items: [
              _buildNotificationTile(
                title: 'Family Updates',
                subtitle: 'Updates from family members and caregivers',
                value: _familyUpdates,
                onChanged: (value) => setState(() => _familyUpdates = value),
                icon: Icons.family_restroom,
              ),
            ],
          ),
          const SizedBox(height: 20),
          _buildNotificationSection(
            title: 'System',
            items: [
              _buildNotificationTile(
                title: 'System Notifications',
                subtitle: 'App updates and system messages',
                value: _systemNotifications,
                onChanged: (value) =>
                    setState(() => _systemNotifications = value),
                icon: Icons.notifications_outlined,
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildNotificationSection({
    required String title,
    required List<Widget> items,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.only(left: 8, bottom: 12),
          child: Text(
            title,
            style: TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.bold,
              color: AppColors.textPrimary.withOpacity(
                0.7,
              ), // deepTeal -> textPrimary
              letterSpacing: 0.5,
            ),
          ),
        ),
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
              for (int i = 0; i < items.length; i++) ...[
                items[i],
                if (i < items.length - 1)
                  Divider(
                    height: 1,
                    indent: 68,
                    color: AppColors.primary.withOpacity(0.1),
                  ),
              ],
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildNotificationTile({
    required String title,
    required String subtitle,
    required bool value,
    required ValueChanged<bool> onChanged,
    required IconData icon,
  }) {
    return ListTile(
      contentPadding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
      leading: Container(
        width: 48,
        height: 48,
        decoration: BoxDecoration(
          color: AppColors.primaryLighter, // surfaceMint -> primaryLighter
          borderRadius: BorderRadius.circular(12),
        ),
        child: Icon(icon, color: AppColors.primary, size: 24),
      ),
      title: Text(
        title,
        style: const TextStyle(
          fontSize: 16,
          fontWeight: FontWeight.w600,
          color: AppColors.textPrimary, // deepTeal -> textPrimary
        ),
      ),
      subtitle: Text(
        subtitle,
        style: TextStyle(
          fontSize: 12,
          color: AppColors.textPrimary.withOpacity(
            0.6,
          ), // deepTeal -> textPrimary
        ),
      ),
      trailing: Switch(
        value: value,
        onChanged: onChanged,
        activeThumbColor: AppColors.primary,
      ),
    );
  }
}
