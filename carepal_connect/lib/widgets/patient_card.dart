import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../core/app_colors.dart';
import '../models/patient_link.dart';

class PatientCard extends StatelessWidget {
  final String patientName;
  final String badgeLabel;
  final Color badgeColor;
  final List<String> permissionLabels;
  final VoidCallback onUnlink;
  final VoidCallback onView;

  const PatientCard._({
    required this.patientName,
    required this.badgeLabel,
    required this.badgeColor,
    required this.permissionLabels,
    required this.onUnlink,
    required this.onView,
  });

  factory PatientCard.clinical({
    required ClinicalRelationship link,
    required VoidCallback onUnlink,
    required VoidCallback onView,
  }) {
    final perms = <String>[];
    if (link.canViewVitals) perms.add('Vitals');
    if (link.canViewActivityLog) perms.add('Activity Log');
    if (link.canViewMedications) perms.add('Medications');
    if (link.canViewAlerts) perms.add('Alerts');
    if (link.canViewAppointments) perms.add('Appointments');

    return PatientCard._(
      patientName: link.patientName,
      badgeLabel: _roleLabel(link.role),
      badgeColor: AppColors.vitalsBlue,
      permissionLabels: perms,
      onUnlink: onUnlink,
      onView: onView,
    );
  }

  factory PatientCard.family({
    required FamilyMemberLink link,
    required VoidCallback onUnlink,
    required VoidCallback onView,
  }) {
    final perms = <String>[];
    if (link.canViewVitals) perms.add('Vitals');
    if (link.canViewActivityLog) perms.add('Activity Log');
    if (link.canViewMedications) perms.add('Medications');
    if (link.canViewAlerts) perms.add('Alerts');

    return PatientCard._(
      patientName: link.patientName,
      badgeLabel: _relLabel(link.relationship),
      badgeColor: AppColors.primary,
      permissionLabels: perms,
      onUnlink: onUnlink,
      onView: onView,
    );
  }

  static String _roleLabel(String role) {
    switch (role) {
      case 'PRIMARY':
        return 'Primary Physician';
      case 'SPECIALIST':
        return 'Specialist';
      case 'NURSE':
        return 'Nurse';
      case 'CONSULTANT':
        return 'Consultant';
      default:
        return role;
    }
  }

  static String _relLabel(String rel) {
    switch (rel) {
      case 'SPOUSE':
        return 'Spouse';
      case 'CHILD':
        return 'Child';
      case 'PARENT':
        return 'Parent';
      case 'SIBLING':
        return 'Sibling';
      default:
        return 'Other';
    }
  }

  String _initials(String name) {
    final parts = name.trim().split(' ');
    if (parts.isEmpty) return '?';
    if (parts.length == 1) return parts[0][0].toUpperCase();
    return '${parts[0][0]}${parts[1][0]}'.toUpperCase();
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AppColors.border),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.03),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                // Avatar
                CircleAvatar(
                  radius: 24,
                  backgroundColor: badgeColor.withOpacity(0.12),
                  child: Text(
                    _initials(patientName),
                    style: GoogleFonts.lexend(
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                      color: badgeColor,
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        patientName,
                        style: GoogleFonts.lexend(
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                          color: AppColors.textPrimary,
                        ),
                      ),
                      const SizedBox(height: 4),
                      // Role/relationship badge
                      Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 8, vertical: 3),
                        decoration: BoxDecoration(
                          color: badgeColor.withOpacity(0.12),
                          borderRadius: BorderRadius.circular(20),
                        ),
                        child: Text(
                          badgeLabel,
                          style: TextStyle(
                            fontSize: 11,
                            fontWeight: FontWeight.w700,
                            color: badgeColor,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
                // Unlink button
                IconButton(
                  icon: const Icon(Icons.link_off,
                      size: 20, color: AppColors.error),
                  onPressed: onUnlink,
                  tooltip: 'Unlink patient',
                ),
              ],
            ),
            // Permission pills
            if (permissionLabels.isNotEmpty) ...[
              const SizedBox(height: 12),
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: permissionLabels
                    .map((perm) => Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 8, vertical: 4),
                          decoration: BoxDecoration(
                            color: AppColors.background,
                            borderRadius: BorderRadius.circular(20),
                            border: Border.all(color: AppColors.border),
                          ),
                          child: Text(
                            perm,
                            style: const TextStyle(
                              fontSize: 11,
                              color: AppColors.textSecondary,
                              fontWeight: FontWeight.w500,
                            ),
                          ),
                        ))
                    .toList(),
              ),
            ],
            const SizedBox(height: 14),
            // View button
            SizedBox(
              width: double.infinity,
              height: 40,
              child: ElevatedButton(
                onPressed: onView,
                style: ElevatedButton.styleFrom(
                  backgroundColor: badgeColor,
                  minimumSize: const Size(double.infinity, 40),
                  padding: const EdgeInsets.symmetric(vertical: 0),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(10),
                  ),
                  textStyle: const TextStyle(
                      fontSize: 14, fontWeight: FontWeight.w600),
                ),
                child: const Text('View',
                    style: TextStyle(color: Colors.white)),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
