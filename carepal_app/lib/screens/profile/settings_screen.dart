import 'package:flutter/material.dart';
import '../../core/app_colors.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  bool _notificationsEnabled = true;
  bool _soundEnabled = true;
  bool _vibrationEnabled = true;
  bool _medicationReminders = true;
  bool _vitalAlerts = true;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: AppColors.surface,
        elevation: 0,
        leading: IconButton(
          icon: Icon(Icons.arrow_back, color: AppColors.textPrimary),
          onPressed: () => Navigator.pop(context),
        ),
        title: Text(
          'Settings',
          style: TextStyle(
            color: AppColors.textPrimary,
            fontSize: 18,
            fontWeight: FontWeight.bold,
          ),
        ),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _buildSection(
              title: 'Notifications',
              children: [
                _buildSwitchTile(
                  title: 'Enable Notifications',
                  subtitle: 'Receive alerts and reminders',
                  value: _notificationsEnabled,
                  onChanged: (val) =>
                      setState(() => _notificationsEnabled = val),
                ),
                _buildSwitchTile(
                  title: 'Sound',
                  subtitle: 'Play sound for notifications',
                  value: _soundEnabled,
                  onChanged: (val) => setState(() => _soundEnabled = val),
                ),
                _buildSwitchTile(
                  title: 'Vibration',
                  subtitle: 'Vibrate on notifications',
                  value: _vibrationEnabled,
                  onChanged: (val) => setState(() => _vibrationEnabled = val),
                ),
              ],
            ),
            const SizedBox(height: 24),
            _buildSection(
              title: 'Reminders',
              children: [
                _buildSwitchTile(
                  title: 'Medication Reminders',
                  subtitle: 'Get reminded to take medications',
                  value: _medicationReminders,
                  onChanged: (val) =>
                      setState(() => _medicationReminders = val),
                ),
                _buildSwitchTile(
                  title: 'Vital Alerts',
                  subtitle: 'Alert on abnormal vital readings',
                  value: _vitalAlerts,
                  onChanged: (val) => setState(() => _vitalAlerts = val),
                ),
              ],
            ),
            const SizedBox(height: 24),
            _buildSection(
              title: 'Data & Privacy',
              children: [
                _buildTile(
                  icon: Icons.cloud_download_outlined,
                  title: 'Export Data',
                  onTap: () => _showComingSoon(context),
                ),
                _buildTile(
                  icon: Icons.delete_outline,
                  title: 'Clear Cache',
                  onTap: () => _showComingSoon(context),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSection({
    required String title,
    required List<Widget> children,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.only(left: 4, bottom: 12),
          child: Text(
            title,
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.bold,
              color: AppColors.textPrimary,
            ),
          ),
        ),
        Container(
          decoration: BoxDecoration(
            color: AppColors.surface,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: AppColors.border),
          ),
          child: Column(
            children: children
                .asMap()
                .entries
                .map(
                  (entry) => Column(
                    children: [
                      if (entry.key > 0)
                        Divider(height: 1, color: AppColors.divider),
                      entry.value,
                    ],
                  ),
                )
                .toList(),
          ),
        ),
      ],
    );
  }

  Widget _buildSwitchTile({
    required String title,
    required String subtitle,
    required bool value,
    required ValueChanged<bool> onChanged,
  }) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w600,
                    color: AppColors.textPrimary,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  subtitle,
                  style: TextStyle(
                    fontSize: 13,
                    color: AppColors.textSecondary,
                  ),
                ),
              ],
            ),
          ),
          Switch(
            value: value,
            onChanged: onChanged,
            activeColor: AppColors.primary,
          ),
        ],
      ),
    );
  }

  Widget _buildTile({
    required IconData icon,
    required String title,
    required VoidCallback onTap,
  }) {
    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: AppColors.primaryLighter,
                borderRadius: BorderRadius.circular(10),
              ),
              child: Icon(icon, color: AppColors.primary, size: 22),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Text(
                title,
                style: TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.w600,
                  color: AppColors.textPrimary,
                ),
              ),
            ),
            Icon(Icons.chevron_right, color: AppColors.textTertiary, size: 20),
          ],
        ),
      ),
    );
  }

  void _showComingSoon(BuildContext context) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: const Text('Coming soon!'),
        backgroundColor: AppColors.primary,
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      ),
    );
  }
}
