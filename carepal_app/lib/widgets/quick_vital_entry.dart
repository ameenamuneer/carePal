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
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
      ),
      child: Form(
        key: _formKey,
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
              onPressed: _handleSubmit,
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.primary,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(vertical: 16),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(16),
                ),
                elevation: 0,
              ),
              child: const Text(
                'Save Readings',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
              ),
            ),
            const SizedBox(height: 20),
          ],
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
    final provider = context.read<VitalsProvider>();
    final authProvider = context.read<AuthProvider>();
    final user = authProvider.user;

    // Use patient profile ID if available
    final patientId = user != null && user['patient_profile'] != null
        ? user['patient_profile']['id'] as int
        : null;

    if (patientId == null) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text('Error: Not logged in')));
      return;
    }

    final vitalTypes = provider.vitalTypes;

    if (vitalTypes.isEmpty) {
      await provider.loadVitalTypes();
    }

    bool anySubmitted = false;

    // Submit BP
    if (_systolicController.text.isNotEmpty &&
        _diastolicController.text.isNotEmpty) {
      try {
        final bpType = provider.vitalTypes.firstWhere((vt) => vt.code == 'BP');
        await provider.createReading(
          patientId: patientId,
          vitalTypeId: bpType.id,
          values: {
            'systolic': int.parse(_systolicController.text),
            'diastolic': int.parse(_diastolicController.text),
          },
          unit: 'mmHg',
          measuredAt: DateTime.now(),
        );
        anySubmitted = true;
      } catch (e) {
        debugPrint('Error submit BP: $e');
      }
    }

    // Submit HR
    if (_hrController.text.isNotEmpty) {
      try {
        final hrType = provider.vitalTypes.firstWhere((vt) => vt.code == 'HR');
        await provider.createReading(
          patientId: patientId,
          vitalTypeId: hrType.id,
          value: double.parse(_hrController.text),
          unit: 'bpm',
          measuredAt: DateTime.now(),
        );
        anySubmitted = true;
      } catch (e) {
        debugPrint('Error submit HR: $e');
      }
    }

    // Submit SpO2
    if (_spo2Controller.text.isNotEmpty) {
      try {
        final spo2Type = provider.vitalTypes.firstWhere(
          (vt) => vt.code == 'SPO2',
        );
        await provider.createReading(
          patientId: patientId,
          vitalTypeId: spo2Type.id,
          value: double.parse(_spo2Controller.text),
          unit: '%',
          measuredAt: DateTime.now(),
        );
        anySubmitted = true;
      } catch (e) {
        debugPrint('Error submit SpO2: $e');
      }
    }

    // Submit Temp
    if (_tempController.text.isNotEmpty) {
      try {
        final tempType = provider.vitalTypes.firstWhere(
          (vt) => vt.code == 'TEMP',
        );
        await provider.createReading(
          patientId: patientId,
          vitalTypeId: tempType.id,
          value: double.parse(_tempController.text),
          unit: '°F',
          measuredAt: DateTime.now(),
        );
        anySubmitted = true;
      } catch (e) {
        debugPrint('Error submit Temp: $e');
      }
    }

    if (anySubmitted && mounted) {
      Navigator.pop(context);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: const Text('Vitals saved successfully'),
          backgroundColor: AppColors.success,
          behavior: SnackBarBehavior.floating,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
        ),
      );
      // Refresh dashboard
      await context.read<DashboardProvider>().loadDashboard();
      await provider.loadReadings(days: 7);
    }
  }
}
