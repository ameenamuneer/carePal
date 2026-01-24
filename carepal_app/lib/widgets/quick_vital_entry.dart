// lib/widgets/quick_vital_entry.dart
// FIXED VERSION - Proper async handling and dashboard refresh

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../core/app_colors.dart';
import '../providers/vitals_provider.dart';
import '../providers/dashboard_provider.dart';
import '../providers/auth_provider.dart';

class QuickVitalEntry extends StatefulWidget {
  const QuickVitalEntry({super.key});

  @override
  State<QuickVitalEntry> createState() => _QuickVitalEntryState();
}

class _QuickVitalEntryState extends State<QuickVitalEntry> {
  final _formKey = GlobalKey<FormState>();
  final _systolicController = TextEditingController();
  final _diastolicController = TextEditingController();
  final _hrController = TextEditingController();
  final _spo2Controller = TextEditingController();
  final _tempController = TextEditingController();

  bool _isSubmitting = false;

  @override
  void dispose() {
    _systolicController.dispose();
    _diastolicController.dispose();
    _hrController.dispose();
    _spo2Controller.dispose();
    _tempController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: EdgeInsets.only(
        left: 24,
        right: 24,
        top: 24,
        bottom: MediaQuery.of(context).viewInsets.bottom + 24,
      ),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
      ),
      child: Form(
        key: _formKey,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    'Quick Vital Entry',
                    style: TextStyle(
                      fontSize: 20,
                      fontWeight: FontWeight.bold,
                      color: AppColors.textPrimary,
                    ),
                  ),
                  IconButton(
                    icon: const Icon(Icons.close),
                    onPressed: () => Navigator.pop(context),
                  ),
                ],
              ),
              const SizedBox(height: 20),
              _buildVitalInput(
                label: 'Blood Pressure',
                controllers: [_systolicController, _diastolicController],
                hint: ['Systolic', 'Diastolic'],
                icon: Icons.favorite,
                color: AppColors.vitalsRed,
              ),
              const SizedBox(height: 16),
              _buildVitalInput(
                label: 'Heart Rate',
                controllers: [_hrController],
                hint: ['bpm'],
                icon: Icons.monitor_heart,
                color: AppColors.vitalsPink,
              ),
              const SizedBox(height: 16),
              _buildVitalInput(
                label: 'Oxygen Saturation',
                controllers: [_spo2Controller],
                hint: ['%'],
                icon: Icons.air,
                color: AppColors.vitalsBlue,
              ),
              const SizedBox(height: 16),
              _buildVitalInput(
                label: 'Temperature',
                controllers: [_tempController],
                hint: ['°F'],
                icon: Icons.thermostat,
                color: AppColors.vitalsOrange,
              ),
              const SizedBox(height: 24),
              ElevatedButton(
                onPressed: _isSubmitting ? null : _handleSubmit,
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppColors.primary,
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(16),
                  ),
                  elevation: 0,
                ),
                child: _isSubmitting
                    ? const SizedBox(
                        height: 20,
                        width: 20,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          valueColor: AlwaysStoppedAnimation<Color>(
                            Colors.white,
                          ),
                        ),
                      )
                    : const Text(
                        'Save Readings',
                        style: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
              ),
              const SizedBox(height: 20),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildVitalInput({
    required String label,
    required List<TextEditingController> controllers,
    required List<String> hint,
    required IconData icon,
    required Color color,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Container(
              padding: const EdgeInsets.all(6),
              decoration: BoxDecoration(
                color: color.withOpacity(0.1),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Icon(icon, color: color, size: 16),
            ),
            const SizedBox(width: 8),
            Text(
              label,
              style: TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w600,
                color: AppColors.textPrimary,
              ),
            ),
          ],
        ),
        const SizedBox(height: 8),
        Row(
          children: controllers.asMap().entries.map((entry) {
            return Expanded(
              child: Padding(
                padding: EdgeInsets.only(
                  right: entry.key < controllers.length - 1 ? 8 : 0,
                ),
                child: TextFormField(
                  controller: entry.value,
                  keyboardType: TextInputType.number,
                  decoration: InputDecoration(
                    hintText: hint[entry.key],
                    filled: true,
                    fillColor: AppColors.background,
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                      borderSide: BorderSide.none,
                    ),
                    contentPadding: const EdgeInsets.symmetric(
                      horizontal: 16,
                      vertical: 12,
                    ),
                  ),
                ),
              ),
            );
          }).toList(),
        ),
      ],
    );
  }

  Future<void> _handleSubmit() async {
    // CRITICAL FIX: Check if any field has data
    if (_systolicController.text.isEmpty &&
        _diastolicController.text.isEmpty &&
        _hrController.text.isEmpty &&
        _spo2Controller.text.isEmpty &&
        _tempController.text.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Please enter at least one vital reading'),
          backgroundColor: AppColors.error,
        ),
      );
      return;
    }

    setState(() => _isSubmitting = true);

    final provider = context.read<VitalsProvider>();
    final dashboardProvider = context.read<DashboardProvider>();
    final authProvider = context.read<AuthProvider>();
    final user = authProvider.user;

    // Use patient profile ID if available
    final patientId = user != null && user['patient_profile'] != null
        ? user['patient_profile']['id'] as int
        : null;

    if (patientId == null) {
      setState(() => _isSubmitting = false);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Error: Patient profile not found'),
          backgroundColor: AppColors.error,
        ),
      );
      return;
    }

    // CRITICAL FIX: Load vital types if empty
    if (provider.vitalTypes.isEmpty) {
      await provider.loadVitalTypes();
    }

    int successCount = 0;
    final now = DateTime.now();

    try {
      // Submit BP
      if (_systolicController.text.isNotEmpty &&
          _diastolicController.text.isNotEmpty) {
        try {
          final systolic = int.tryParse(_systolicController.text);
          final diastolic = int.tryParse(_diastolicController.text);

          if (systolic == null || diastolic == null) {
            throw Exception('Invalid blood pressure values');
          }

          final bpType = provider.vitalTypes.firstWhere(
            (vt) => vt.code == 'BP',
            orElse: () => throw Exception('BP vital type not found'),
          );

          final success = await provider.createReading(
            patientId: patientId,
            vitalTypeId: bpType.id,
            values: {'systolic': systolic, 'diastolic': diastolic},
            unit: 'mmHg',
            measuredAt: now,
          );

          if (success) successCount++;
        } catch (e) {
          debugPrint('Error submitting BP: $e');
        }
      }

      // Submit HR
      if (_hrController.text.isNotEmpty) {
        try {
          final hr = double.tryParse(_hrController.text);

          if (hr == null) {
            throw Exception('Invalid heart rate value');
          }

          final hrType = provider.vitalTypes.firstWhere(
            (vt) => vt.code == 'HR',
            orElse: () => throw Exception('HR vital type not found'),
          );

          final success = await provider.createReading(
            patientId: patientId,
            vitalTypeId: hrType.id,
            value: hr,
            unit: 'bpm',
            measuredAt: now,
          );

          if (success) successCount++;
        } catch (e) {
          debugPrint('Error submitting HR: $e');
        }
      }

      // Submit SpO2
      if (_spo2Controller.text.isNotEmpty) {
        try {
          final spo2 = double.tryParse(_spo2Controller.text);

          if (spo2 == null) {
            throw Exception('Invalid SpO2 value');
          }

          final spo2Type = provider.vitalTypes.firstWhere(
            (vt) => vt.code == 'SPO2',
            orElse: () => throw Exception('SPO2 vital type not found'),
          );

          final success = await provider.createReading(
            patientId: patientId,
            vitalTypeId: spo2Type.id,
            value: spo2,
            unit: '%',
            measuredAt: now,
          );

          if (success) successCount++;
        } catch (e) {
          debugPrint('Error submitting SpO2: $e');
        }
      }

      // Submit Temperature
      if (_tempController.text.isNotEmpty) {
        try {
          final temp = double.tryParse(_tempController.text);

          if (temp == null) {
            throw Exception('Invalid temperature value');
          }

          final tempType = provider.vitalTypes.firstWhere(
            (vt) => vt.code == 'TEMP',
            orElse: () => throw Exception('TEMP vital type not found'),
          );

          final success = await provider.createReading(
            patientId: patientId,
            vitalTypeId: tempType.id,
            value: temp,
            unit: '°F',
            measuredAt: now,
          );

          if (success) successCount++;
        } catch (e) {
          debugPrint('Error submitting Temperature: $e');
        }
      }

      // CRITICAL FIX: Refresh dashboard AFTER all submissions
      if (successCount > 0) {
        // Use post-frame callback to avoid setState during build
        WidgetsBinding.instance.addPostFrameCallback((_) {
          dashboardProvider.requestRefresh();
        });
      }
    } catch (e) {
      debugPrint('Error in handleSubmit: $e');
    }

    setState(() => _isSubmitting = false);

    if (!mounted) return;

    // Show result
    if (successCount > 0) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Row(
            children: [
              Icon(Icons.check_circle, color: Colors.white),
              const SizedBox(width: 12),
              Text('$successCount reading(s) saved successfully'),
            ],
          ),
          backgroundColor: AppColors.success,
          behavior: SnackBarBehavior.floating,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
          ),
        ),
      );
      Navigator.pop(context, true);
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Failed to save readings. Please try again.'),
          backgroundColor: AppColors.error,
        ),
      );
    }
  }
}
