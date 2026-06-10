import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';
import '../core/app_colors.dart';
import '../providers/auth_provider.dart';
import '../providers/patient_provider.dart';
import '../services/link_service.dart';

class LinkPatientScreen extends StatefulWidget {
  const LinkPatientScreen({super.key});

  @override
  State<LinkPatientScreen> createState() => _LinkPatientScreenState();
}

class _LinkPatientScreenState extends State<LinkPatientScreen> {
  final _formKey = GlobalKey<FormState>();
  final _patientIdCtrl = TextEditingController();
  bool _isLoading = false;

  // Doctor roles
  static const _doctorRoles = [
    ('PRIMARY', 'Primary Physician'),
    ('SPECIALIST', 'Specialist'),
    ('NURSE', 'Nurse'),
    ('CONSULTANT', 'Consultant'),
  ];

  // Family relationships
  static const _familyRelationships = [
    ('SPOUSE', 'Spouse'),
    ('CHILD', 'Child'),
    ('PARENT', 'Parent'),
    ('SIBLING', 'Sibling'),
    ('OTHER', 'Other'),
  ];

  String _selectedRole = 'PRIMARY';
  String _selectedRelationship = 'CHILD';

  @override
  void dispose() {
    _patientIdCtrl.dispose();
    super.dispose();
  }

  Future<void> _linkPatient() async {
    if (!_formKey.currentState!.validate()) return;

    final patientId = int.tryParse(_patientIdCtrl.text.trim());
    if (patientId == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Please enter a valid numeric Patient ID'),
          backgroundColor: AppColors.error,
        ),
      );
      return;
    }

    setState(() => _isLoading = true);

    try {
      final authProvider = context.read<AuthProvider>();
      final patientProvider = context.read<PatientProvider>();
      final service = LinkService();

      if (authProvider.isDoctor) {
        final link = await service.linkPatientAsDoctor(patientId, _selectedRole);
        await patientProvider.addClinicalLink(link);
      } else {
        final link = await service.linkPatientAsFamily(
          authProvider.userId,
          patientId,
          _selectedRelationship,
        );
        await patientProvider.addFamilyLink(link);
      }

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Patient linked successfully!'),
            backgroundColor: AppColors.success,
          ),
        );
        Navigator.of(context).pop();
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(e.toString().replaceFirst('Exception: ', '')),
            backgroundColor: AppColors.error,
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final authProvider = context.watch<AuthProvider>();
    final isDoctor = authProvider.isDoctor;

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: Text(
          'Link a Patient',
          style: GoogleFonts.lexend(
            fontSize: 20,
            fontWeight: FontWeight.bold,
            color: AppColors.primaryDark,
          ),
        ),
        backgroundColor: AppColors.surface,
        elevation: 0,
        leading: const BackButton(color: AppColors.primaryDark),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Info card
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: AppColors.primaryLighter,
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.info_outline,
                        color: AppColors.primary, size: 20),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        isDoctor
                            ? 'Enter the patient\'s profile ID to establish a clinical relationship.'
                            : 'Enter the patient\'s profile ID to link as a family member.',
                        style: const TextStyle(
                          fontSize: 13,
                          color: AppColors.primary,
                          height: 1.4,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 28),
              Text(
                'Patient ID',
                style: GoogleFonts.lexend(
                  fontSize: 15,
                  fontWeight: FontWeight.w600,
                  color: AppColors.textPrimary,
                ),
              ),
              const SizedBox(height: 8),
              TextFormField(
                controller: _patientIdCtrl,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(
                  labelText: 'Patient Profile ID',
                  hintText: 'e.g. 42',
                  prefixIcon: Icon(Icons.badge_outlined),
                ),
                validator: (v) {
                  if (v == null || v.isEmpty) return 'Enter Patient ID';
                  if (int.tryParse(v) == null) return 'Must be a number';
                  return null;
                },
              ),
              const SizedBox(height: 28),
              Text(
                isDoctor ? 'Your Role' : 'Relationship',
                style: GoogleFonts.lexend(
                  fontSize: 15,
                  fontWeight: FontWeight.w600,
                  color: AppColors.textPrimary,
                ),
              ),
              const SizedBox(height: 12),
              if (isDoctor) ...[
                Wrap(
                  spacing: 10,
                  runSpacing: 10,
                  children: _doctorRoles.map(((String, String) role) {
                    final isSelected = _selectedRole == role.$1;
                    return GestureDetector(
                      onTap: () =>
                          setState(() => _selectedRole = role.$1),
                      child: _SelectionChip(
                        label: role.$2,
                        selected: isSelected,
                      ),
                    );
                  }).toList(),
                ),
              ] else ...[
                Wrap(
                  spacing: 10,
                  runSpacing: 10,
                  children: _familyRelationships.map(((String, String) rel) {
                    final isSelected = _selectedRelationship == rel.$1;
                    return GestureDetector(
                      onTap: () =>
                          setState(() => _selectedRelationship = rel.$1),
                      child: _SelectionChip(
                        label: rel.$2,
                        selected: isSelected,
                      ),
                    );
                  }).toList(),
                ),
              ],
              const SizedBox(height: 40),
              SizedBox(
                width: double.infinity,
                height: 52,
                child: ElevatedButton(
                  onPressed: _isLoading ? null : _linkPatient,
                  child: _isLoading
                      ? const SizedBox(
                          width: 22,
                          height: 22,
                          child: CircularProgressIndicator(
                            color: Colors.white,
                            strokeWidth: 2,
                          ),
                        )
                      : const Text('Link Patient'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _SelectionChip extends StatelessWidget {
  final String label;
  final bool selected;

  const _SelectionChip({required this.label, required this.selected});

  @override
  Widget build(BuildContext context) {
    return AnimatedContainer(
      duration: const Duration(milliseconds: 200),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      decoration: BoxDecoration(
        color: selected ? AppColors.primary : AppColors.surface,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(
          color: selected ? AppColors.primary : AppColors.border,
          width: selected ? 2 : 1.5,
        ),
      ),
      child: Text(
        label,
        style: GoogleFonts.lexend(
          fontSize: 13,
          fontWeight: FontWeight.w600,
          color: selected ? Colors.white : AppColors.textPrimary,
        ),
      ),
    );
  }
}
