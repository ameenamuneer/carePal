import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';
import '../core/app_colors.dart';
import '../providers/auth_provider.dart';
import '../providers/patient_provider.dart';
import '../services/link_service.dart';
import '../widgets/patient_card.dart';
import 'link_patient_screen.dart';

class PatientsScreen extends StatelessWidget {
  const PatientsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final patientProvider = context.watch<PatientProvider>();
    final authProvider = context.watch<AuthProvider>();
    final isDoctor = authProvider.isDoctor;

    final hasPatients = isDoctor
        ? patientProvider.clinicalLinks.isNotEmpty
        : patientProvider.familyLinks.isNotEmpty;

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: AppColors.background,
        elevation: 0,
        automaticallyImplyLeading: false,
        title: Text(
          'My Patients',
          style: GoogleFonts.lexend(
            fontSize: 20,
            fontWeight: FontWeight.bold,
            color: AppColors.primaryDark,
          ),
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.person_add_outlined,
                color: AppColors.primary),
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => const LinkPatientScreen()),
            ),
          ),
        ],
      ),
      body: patientProvider.isLoading
          ? const Center(
              child: CircularProgressIndicator(color: AppColors.primary))
          : !hasPatients
              ? _buildEmptyState(context)
              : RefreshIndicator(
                  color: AppColors.primary,
                  onRefresh: () =>
                      patientProvider.loadLinks(authProvider.userType),
                  child: ListView(
                    padding: const EdgeInsets.all(16),
                    children: [
                      if (isDoctor)
                        ...patientProvider.clinicalLinks.map((link) =>
                            PatientCard.clinical(
                              link: link,
                              onUnlink: () =>
                                  _confirmUnlink(context, link.id, true),
                              onView: () {
                                patientProvider.setActivePatient(
                                    link.patient, link.patientName);
                              },
                            ))
                      else
                        ...patientProvider.familyLinks.map((link) =>
                            PatientCard.family(
                              link: link,
                              onUnlink: () =>
                                  _confirmUnlink(context, link.id, false),
                              onView: () {
                                patientProvider.setActivePatient(
                                    link.patient, link.patientName);
                              },
                            )),
                    ],
                  ),
                ),
    );
  }

  Widget _buildEmptyState(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              width: 80,
              height: 80,
              decoration: BoxDecoration(
                color: AppColors.primaryLighter,
                borderRadius: BorderRadius.circular(20),
              ),
              child: const Icon(Icons.people_outline,
                  size: 40, color: AppColors.primary),
            ),
            const SizedBox(height: 20),
            Text(
              'No Patients Linked',
              style: GoogleFonts.lexend(
                fontSize: 20,
                fontWeight: FontWeight.bold,
                color: AppColors.textPrimary,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'Link your first patient to start\nmonitoring their health data.',
              textAlign: TextAlign.center,
              style: const TextStyle(
                  color: AppColors.textSecondary, fontSize: 14),
            ),
            const SizedBox(height: 28),
            SizedBox(
              width: 200,
              child: ElevatedButton.icon(
                onPressed: () => Navigator.of(context).push(
                  MaterialPageRoute(
                      builder: (_) => const LinkPatientScreen()),
                ),
                icon: const Icon(Icons.add),
                label: const Text('Link Patient'),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _confirmUnlink(
      BuildContext context, int linkId, bool isClinical) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Unlink Patient'),
        content: const Text(
            'Are you sure you want to remove this patient link? You will lose access to their data.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            style: TextButton.styleFrom(foregroundColor: AppColors.error),
            child: const Text('Unlink'),
          ),
        ],
      ),
    );

    if (confirmed != true) return;

    try {
      final service = LinkService();
      final patientProvider = context.read<PatientProvider>();
      if (isClinical) {
        await service.unlinkPatient(linkId);
        await patientProvider.removeClinicalLink(linkId);
      } else {
        await service.unlinkFamilyPatient(linkId);
        await patientProvider.removeFamilyLink(linkId);
      }
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Patient unlinked.')),
        );
      }
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(e.toString().replaceFirst('Exception: ', '')),
            backgroundColor: AppColors.error,
          ),
        );
      }
    }
  }
}
