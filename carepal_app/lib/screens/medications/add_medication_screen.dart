import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:font_awesome_flutter/font_awesome_flutter.dart';
import 'package:intl/intl.dart';
import '../../core/app_colors.dart';
import '../../providers/medication_provider.dart';
import '../../providers/auth_provider.dart';

class AddMedicationScreen extends StatefulWidget {
  const AddMedicationScreen({super.key});

  @override
  State<AddMedicationScreen> createState() => _AddMedicationScreenState();
}

class _AddMedicationScreenState extends State<AddMedicationScreen> {
  final _formKey = GlobalKey<FormState>();
  final _nameController = TextEditingController();
  final _dosageController = TextEditingController();
  final _instructionsController = TextEditingController();

  String _selectedForm = 'Pill';
  String _selectedRoute = 'Oral';
  String _selectedFrequency = 'Once Daily';
  DateTime _startDate = DateTime.now();
  DateTime? _endDate;
  bool _isCritical = false;

  // Mappings for Backend Enums
  final Map<String, String> _formMapping = {
    'Pill': 'TABLET',
    'Capsule': 'CAPSULE',
    'Liquid': 'LIQUID',
    'Injection': 'INJECTION',
    'Drops': 'DROPS',
    'Inhaler': 'INHALER',
    'Spray': 'SPRAY',
    'Patch': 'PATCH',
    'Cream': 'CREAM',
    'Powder': 'POWDER',
    'Other': 'OTHER',
  };

  final Map<String, String> _routeMapping = {
    'Oral': 'ORAL',
    'Sublingual': 'SUBLINGUAL',
    'Topical': 'TOPICAL',
    'Inhalation': 'INHALATION',
    'Intravenous': 'INJECTION_IV',
    'Intramuscular': 'INJECTION_IM',
    'Subcutaneous': 'INJECTION_SC',
    'Rectal': 'RECTAL',
    'Eye': 'OPHTHALMIC',
    'Ear': 'OTIC',
    'Nasal': 'NASAL',
  };

  final Map<String, String> _frequencyMapping = {
    'Once Daily': 'ONCE_DAILY',
    'Twice Daily': 'TWICE_DAILY',
    '3x Daily': 'THREE_TIMES_DAILY',
    '4x Daily': 'FOUR_TIMES_DAILY',
    'Every 4 Hours': 'EVERY_4_HOURS',
    'Every 6 Hours': 'EVERY_6_HOURS',
    'Every 8 Hours': 'EVERY_8_HOURS',
    'Every 12 Hours': 'EVERY_12_HOURS',
    'Weekly': 'WEEKLY',
    'Twice Weekly': 'TWICE_WEEKLY',
    'Monthly': 'MONTHLY',
    'As Needed': 'AS_NEEDED',
  };

  @override
  void dispose() {
    _nameController.dispose();
    _dosageController.dispose();
    _instructionsController.dispose();
    super.dispose();
  }

  Future<void> _selectDate(BuildContext context, bool isStart) async {
    final picked = await showDatePicker(
      context: context,
      initialDate: isStart ? _startDate : (_endDate ?? DateTime.now()),
      firstDate: DateTime.now().subtract(const Duration(days: 365)),
      lastDate: DateTime.now().add(const Duration(days: 365 * 5)),
      builder: (context, child) {
        return Theme(
          data: Theme.of(context).copyWith(
            colorScheme: ColorScheme.light(
              primary: AppColors.primary,
              onPrimary: Colors.white,
              onSurface: AppColors.textPrimary,
            ),
          ),
          child: child!,
        );
      },
    );

    if (picked != null) {
      setState(() {
        if (isStart) {
          _startDate = picked;
        } else {
          _endDate = picked;
        }
      });
    }
  }

  Future<void> _saveMedication() async {
    if (_formKey.currentState!.validate()) {
      final provider = context.read<MedicationProvider>();
      final authProvider = context.read<AuthProvider>();

      // Get patient ID
      final user = authProvider.user;
      final patientProfile = user?['patient_profile'];
      final patientId = patientProfile?['id'];

      if (patientId == null) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: const Text('Error: Could not determine Patient ID'),
            backgroundColor: AppColors.error,
          ),
        );
        return;
      }

      final medicationData = {
        'patient': patientId,
        'medication_name': _nameController.text,
        'dosage': _dosageController.text,
        'form': _formMapping[_selectedForm],
        'route': _routeMapping[_selectedRoute],
        'frequency': _frequencyMapping[_selectedFrequency],
        'instructions': _instructionsController.text.isEmpty
            ? 'Take as prescribed'
            : _instructionsController.text,
        'start_date': DateFormat('yyyy-MM-dd').format(_startDate),
        'end_date': _endDate != null
            ? DateFormat('yyyy-MM-dd').format(_endDate!)
            : null,
        'is_critical': _isCritical,
        'status': 'ACTIVE',
        // Optional fields that might be needed by strict serializers, sending safe defaults
        'quantity_prescribed': 0,
        'quantity_remaining': 0,
      };

      final success = await provider.addMedication(medicationData);

      if (success && mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: const Text('Medication added successfully'),
            backgroundColor: AppColors.success,
            behavior: SnackBarBehavior.floating,
          ),
        );
        Navigator.pop(context);
      } else if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(provider.error ?? 'Failed to add medication'),
            backgroundColor: AppColors.error,
            behavior: SnackBarBehavior.floating,
          ),
        );
      }
    }
  }

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
          'Add Medication',
          style: TextStyle(
            color: AppColors.textPrimary,
            fontWeight: FontWeight.bold,
          ),
        ),
      ),
      body: Consumer<MedicationProvider>(
        builder: (context, provider, _) {
          return SingleChildScrollView(
            padding: const EdgeInsets.all(20),
            child: Form(
              key: _formKey,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  _buildSectionTitle('Basic Information'),
                  const SizedBox(height: 16),
                  _buildTextField(
                    controller: _nameController,
                    label: 'Medication Name',
                    icon: FontAwesomeIcons.pills,
                    validator: (v) => v?.isEmpty == true ? 'Required' : null,
                  ),
                  const SizedBox(height: 16),
                  Row(
                    children: [
                      Expanded(
                        child: _buildTextField(
                          controller: _dosageController,
                          label: 'Dosage',
                          icon: FontAwesomeIcons.prescription,
                          hint: 'e.g. 500mg',
                          validator: (v) =>
                              v?.isEmpty == true ? 'Required' : null,
                        ),
                      ),
                      const SizedBox(width: 16),
                      Expanded(
                        child: _buildDropdown(
                          value: _selectedFrequency,
                          items: _frequencyMapping.keys.toList(),
                          label: 'Frequency',
                          onChanged: (v) =>
                              setState(() => _selectedFrequency = v!),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 24),

                  _buildSectionTitle('Details'),
                  const SizedBox(height: 16),
                  Row(
                    children: [
                      Expanded(
                        child: _buildDropdown(
                          value: _selectedForm,
                          items: _formMapping.keys.toList(),
                          label: 'Form',
                          onChanged: (v) => setState(() => _selectedForm = v!),
                        ),
                      ),
                      const SizedBox(width: 16),
                      Expanded(
                        child: _buildDropdown(
                          value: _selectedRoute,
                          items: _routeMapping.keys.toList(),
                          label: 'Route',
                          onChanged: (v) => setState(() => _selectedRoute = v!),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 24),

                  _buildSectionTitle('Schedule'),
                  const SizedBox(height: 16),
                  Row(
                    children: [
                      Expanded(
                        child: _buildDatePicker(
                          label: 'Start Date',
                          date: _startDate,
                          onTap: () => _selectDate(context, true),
                        ),
                      ),
                      const SizedBox(width: 16),
                      Expanded(
                        child: _buildDatePicker(
                          label: 'End Date',
                          date: _endDate,
                          onTap: () => _selectDate(context, false),
                          isOptional: true,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 24),

                  _buildSectionTitle('Additional Info'),
                  const SizedBox(height: 16),
                  _buildTextField(
                    controller: _instructionsController,
                    label: 'Instructions',
                    icon: Icons.notes,
                    maxLines: 3,
                    hint: 'e.g. Take with food',
                    // Optional field in UI, but we send default if empty
                  ),
                  const SizedBox(height: 16),
                  SwitchListTile(
                    value: _isCritical,
                    onChanged: (v) => setState(() => _isCritical = v),
                    title: const Text('Critical Medication'),
                    subtitle: const Text('Mark as high priority'),
                    secondary: Container(
                      padding: const EdgeInsets.all(8),
                      decoration: BoxDecoration(
                        color: _isCritical
                            ? AppColors.error.withOpacity(0.1)
                            : Colors.grey.withOpacity(0.1),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Icon(
                        Icons.warning_amber_rounded,
                        color: _isCritical ? AppColors.error : Colors.grey,
                      ),
                    ),
                    contentPadding: EdgeInsets.zero,
                    activeColor: AppColors.error,
                  ),
                  const SizedBox(height: 32),

                  ElevatedButton(
                    onPressed: provider.isLoading ? null : _saveMedication,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppColors.primary,
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(vertical: 16),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(16),
                      ),
                      elevation: 2,
                    ),
                    child: provider.isLoading
                        ? const SizedBox(
                            width: 24,
                            height: 24,
                            child: CircularProgressIndicator(
                              color: Colors.white,
                              strokeWidth: 2,
                            ),
                          )
                        : const Text(
                            'Add Medication',
                            style: TextStyle(
                              fontSize: 16,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                  ),
                  const SizedBox(height: 20),
                ],
              ),
            ),
          );
        },
      ),
    );
  }

  Widget _buildSectionTitle(String title) {
    return Text(
      title,
      style: TextStyle(
        fontSize: 18,
        fontWeight: FontWeight.bold,
        color: AppColors.textPrimary,
      ),
    );
  }

  Widget _buildTextField({
    required TextEditingController controller,
    required String label,
    required IconData icon,
    String? hint,
    int maxLines = 1,
    String? Function(String?)? validator,
  }) {
    return TextFormField(
      controller: controller,
      maxLines: maxLines,
      validator: validator,
      decoration: InputDecoration(
        labelText: label,
        hintText: hint,
        prefixIcon: Icon(icon, color: AppColors.textSecondary, size: 20),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide(color: AppColors.border),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide(color: AppColors.border),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide(color: AppColors.primary, width: 2),
        ),
        filled: true,
        fillColor: AppColors.surface,
      ),
    );
  }

  Widget _buildDropdown({
    required String value,
    required List<String> items,
    required String label,
    required void Function(String?) onChanged,
  }) {
    return DropdownButtonFormField<String>(
      value: value,
      items: items
          .map((e) => DropdownMenuItem(value: e, child: Text(e)))
          .toList(),
      onChanged: onChanged,
      decoration: InputDecoration(
        labelText: label,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide(color: AppColors.border),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide(color: AppColors.border),
        ),
        filled: true,
        fillColor: AppColors.surface,
      ),
    );
  }

  Widget _buildDatePicker({
    required String label,
    required DateTime? date,
    required VoidCallback onTap,
    bool isOptional = false,
  }) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 16),
        decoration: BoxDecoration(
          color: AppColors.surface,
          border: Border.all(color: AppColors.border),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              label,
              style: TextStyle(color: AppColors.textSecondary, fontSize: 12),
            ),
            const SizedBox(height: 4),
            Row(
              children: [
                Icon(Icons.calendar_today, size: 16, color: AppColors.primary),
                const SizedBox(width: 8),
                Text(
                  date != null
                      ? DateFormat('MMM dd, yyyy').format(date)
                      : (isOptional ? 'Optional' : 'Select Date'),
                  style: TextStyle(
                    color: date != null
                        ? AppColors.textPrimary
                        : AppColors.textTertiary,
                    fontWeight: date != null
                        ? FontWeight.w500
                        : FontWeight.normal,
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
