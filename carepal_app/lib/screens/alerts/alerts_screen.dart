import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:intl/intl.dart';
import '../../core/app_colors.dart';
import '../../providers/dashboard_provider.dart';

class AlertsScreen extends StatelessWidget {
  const AlertsScreen({super.key});

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
          'Alerts & Notifications',
          style: TextStyle(
            color: AppColors.textPrimary,
            fontSize: 18,
            fontWeight: FontWeight.bold,
          ),
        ),
        actions: [
          IconButton(
            icon: Icon(
              Icons.notifications_off_outlined,
              color: AppColors.textSecondary,
            ),
            onPressed: () {
              // TODO: Mark all as read
            },
          ),
        ],
      ),
      body: Consumer<DashboardProvider>(
        builder: (context, provider, _) {
          // Mock alerts data (replace with actual backend data)
          final alerts = _getMockAlerts();

          if (alerts.isEmpty) {
            return _buildEmptyState();
          }

          return ListView.builder(
            padding: const EdgeInsets.all(20),
            itemCount: alerts.length,
            itemBuilder: (context, index) {
              return _buildAlertCard(alerts[index]);
            },
          );
        },
      ),
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.notifications_none_rounded,
            size: 80,
            color: AppColors.textTertiary,
          ),
          const SizedBox(height: 16),
          Text(
            'No alerts',
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.bold,
              color: AppColors.textPrimary,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'You\'re all caught up!',
            style: TextStyle(fontSize: 14, color: AppColors.textSecondary),
          ),
        ],
      ),
    );
  }

  Widget _buildAlertCard(Map<String, dynamic> alert) {
    final severity = alert['severity'] as String;
    Color color = AppColors.primary;
    IconData icon = Icons.info_outline;

    switch (severity) {
      case 'CRITICAL':
        color = AppColors.error;
        icon = Icons.error_outline;
        break;
      case 'HIGH':
        color = AppColors.alert;
        icon = Icons.warning_amber_rounded;
        break;
      case 'MEDIUM':
        color = AppColors.warning;
        icon = Icons.notifications_active_outlined;
        break;
      case 'LOW':
        color = AppColors.success;
        icon = Icons.check_circle_outline;
        break;
    }

    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: color.withOpacity(0.3), width: 1.5),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.03),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: color.withOpacity(0.1),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Icon(icon, color: color, size: 24),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        alert['title'],
                        style: TextStyle(
                          fontSize: 15,
                          fontWeight: FontWeight.bold,
                          color: AppColors.textPrimary,
                        ),
                      ),
                    ),
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 8,
                        vertical: 4,
                      ),
                      decoration: BoxDecoration(
                        color: color.withOpacity(0.1),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Text(
                        severity,
                        style: TextStyle(
                          fontSize: 10,
                          fontWeight: FontWeight.bold,
                          color: color,
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                Text(
                  alert['message'],
                  style: TextStyle(
                    fontSize: 13,
                    color: AppColors.textSecondary,
                    height: 1.4,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  DateFormat(
                    'MMM dd, yyyy • hh:mm a',
                  ).format(alert['timestamp']),
                  style: TextStyle(fontSize: 11, color: AppColors.textTertiary),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  List<Map<String, dynamic>> _getMockAlerts() {
    return [
      {
        'severity': 'HIGH',
        'title': 'Blood Pressure Alert',
        'message':
            'Your blood pressure reading of 145/95 is higher than normal. Please consult your doctor.',
        'timestamp': DateTime.now().subtract(const Duration(hours: 2)),
      },
      {
        'severity': 'MEDIUM',
        'title': 'Medication Reminder',
        'message': 'Don\'t forget to take Lisinopril 10mg at 8:00 PM',
        'timestamp': DateTime.now().subtract(const Duration(hours: 4)),
      },
      {
        'severity': 'LOW',
        'title': 'Daily Check Complete',
        'message':
            'Great job! You\'ve completed all vitals readings for today.',
        'timestamp': DateTime.now().subtract(const Duration(hours: 6)),
      },
    ];
  }
}
