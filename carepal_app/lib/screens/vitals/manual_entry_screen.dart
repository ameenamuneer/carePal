import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../core/app_colors.dart';
import '../../providers/vitals_provider.dart';

class ManualEntryScreen extends StatefulWidget {
  final String vitalCode;
  final String vitalName;
  final Color color;

  const ManualEntryScreen({
    super.key,
    required this.vitalCode,
    required this.vitalName,
    required this.color,
  });

  @override
  State<ManualEntryScreen> createState() => _ManualEntryScreenState();
}

class _ManualEntryScreenState extends State<ManualEntryScreen> {
  final _formKey = GlobalKey<FormState>();

  // Controllers for different vital types
  final _valueController = TextEditingController();
  final _systolicController = TextEditingController();
  final _diastolicController = TextEditingController();
  final _notesController = TextEditingController();

  DateTime _selectedDateTime = DateTime.now();
  bool _isSubmitting = false;

  @override
  void dispose() {
    _valueController.dispose();
    _systolicController.dispose();
    _diastolicController.dispose();
    _notesController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: AppColors.surface,
        elevation: 0,
        leading: IconButton(
          icon: Icon(Icons.close, color: AppColors.textPrimary),
          onPressed: () => Navigator.pop(context),
        ),
        title: Text(
          'Add ${widget.vitalName}',
          style: TextStyle(
            color: AppColors.textPrimary,
            fontSize: 18,
            fontWeight: FontWeight.bold,
          ),
        ),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Date & Time Picker
              _buildDateTimePicker(),
              const SizedBox(height: 24),

              // Value Input Fields
              Container(
                padding: const EdgeInsets.all(24),
                decoration: BoxDecoration(
                  color: AppColors.surface,
                  borderRadius: BorderRadius.circular(24),
                  border: Border.all(
                    color: widget.color.withOpacity(0.2),
                    width: 1,
                  ),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Reading',
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.bold,
                        color: AppColors.textPrimary,
                      ),
                    ),
                    const SizedBox(height: 20),
                    _buildInputFields(),
                  ],
                ),
              ),

              const SizedBox(height: 24),

              // Notes (Optional)
              Container(
                padding: const EdgeInsets.all(24),
                decoration: BoxDecoration(
                  color: AppColors.surface,
                  borderRadius: BorderRadius.circular(24),
                  border: Border.all(color: AppColors.border, width: 1),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Notes (Optional)',
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.bold,
                        color: AppColors.textPrimary,
                      ),
                    ),
                    const SizedBox(height: 16),
                    TextFormField(
                      controller: _notesController,
                      maxLines: 3,
                      style: const TextStyle(fontSize: 16),
                      decoration: InputDecoration(
                        hintText: 'Add any additional notes...',
                        filled: true,
                        fillColor: AppColors.primaryLighter,
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(16),
                          borderSide: BorderSide.none,
                        ),
                        contentPadding: const EdgeInsets.all(16),
                      ),
                    ),
                  ],
                ),
              ),

              const SizedBox(height: 32),

              // Submit Button
              _isSubmitting
                  ? const Center(child: CircularProgressIndicator())
                  : ElevatedButton(
                      onPressed: _handleSubmit,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: widget.color,
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(vertical: 18),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(16),
                        ),
                        elevation: 0,
                      ),
                      child: const Text(
                        'SAVE READING',
                        style: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w600,
                          letterSpacing: 1,
                        ),
                      ),
                    ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildDateTimePicker() {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AppColors.border, width: 1),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Date & Time',
            style: TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w600,
              color: AppColors.textSecondary,
            ),
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: GestureDetector(
                  onTap: _selectDate,
                  child: Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: AppColors.primaryLighter,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Row(
                      children: [
                        Icon(
                          Icons.calendar_today,
                          color: AppColors.primary,
                          size: 20,
                        ),
                        const SizedBox(width: 12),
                        Text(
                          _formatDate(_selectedDateTime),
                          style: TextStyle(
                            fontSize: 15,
                            fontWeight: FontWeight.w600,
                            color: AppColors.textPrimary,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: GestureDetector(
                  onTap: _selectTime,
                  child: Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: AppColors.primaryLighter,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Row(
                      children: [
                        Icon(
                          Icons.access_time,
                          color: AppColors.primary,
                          size: 20,
                        ),
                        const SizedBox(width: 12),
                        Text(
                          _formatTime(_selectedDateTime),
                          style: TextStyle(
                            fontSize: 15,
                            fontWeight: FontWeight.w600,
                            color: AppColors.textPrimary,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildInputFields() {
    if (widget.vitalCode == 'BP') {
      return Column(
        children: [
          TextFormField(
            controller: _systolicController,
            keyboardType: TextInputType.number,
            style: const TextStyle(fontSize: 16),
            decoration: InputDecoration(
              labelText: 'Systolic',
              hintText: 'e.g., 120',
              filled: true,
              fillColor: AppColors.primaryLighter,
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(16),
                borderSide: BorderSide.none,
              ),
              prefixIcon: Icon(Icons.arrow_upward, color: widget.color),
            ),
            validator: (value) {
              if (value == null || value.isEmpty) {
                return 'Required';
              }
              final num = int.tryParse(value);
              if (num == null || num < 50 || num > 250) {
                return 'Enter valid value (50-250)';
              }
              return null;
            },
          ),
          const SizedBox(height: 16),
          TextFormField(
            controller: _diastolicController,
            keyboardType: TextInputType.number,
            style: const TextStyle(fontSize: 16),
            decoration: InputDecoration(
              labelText: 'Diastolic',
              hintText: 'e.g., 80',
              filled: true,
              fillColor: AppColors.primaryLighter,
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(16),
                borderSide: BorderSide.none,
              ),
              prefixIcon: Icon(Icons.arrow_downward, color: widget.color),
            ),
            validator: (value) {
              if (value == null || value.isEmpty) {
                return 'Required';
              }
              final num = int.tryParse(value);
              if (num == null || num < 30 || num > 150) {
                return 'Enter valid value (30-150)';
              }
              return null;
            },
          ),
        ],
      );
    }

    // Single value input for other vitals
    return TextFormField(
      controller: _valueController,
      keyboardType: TextInputType.number,
      style: const TextStyle(fontSize: 16),
      decoration: InputDecoration(
        labelText: 'Value',
        hintText: _getHintText(),
        filled: true,
        fillColor: AppColors.primaryLighter,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: BorderSide.none,
        ),
        prefixIcon: Icon(Icons.edit, color: widget.color),
        suffixText: _getUnit(),
      ),
      validator: (value) {
        if (value == null || value.isEmpty) {
          return 'Required';
        }
        final num = double.tryParse(value);
        if (num == null) {
          return 'Enter valid number';
        }
        return null;
      },
    );
  }

  String _getHintText() {
    switch (widget.vitalCode) {
      case 'HR':
        return 'e.g., 72';
      case 'SPO2':
        return 'e.g., 98';
      case 'TEMP':
        return 'e.g., 98.6';
      default:
        return 'Enter value';
    }
  }

  String _getUnit() {
    switch (widget.vitalCode) {
      case 'HR':
        return 'bpm';
      case 'SPO2':
        return '%';
      case 'TEMP':
        return '°F';
      default:
        return '';
    }
  }

  Future<void> _selectDate() async {
    final date = await showDatePicker(
      context: context,
      initialDate: _selectedDateTime,
      firstDate: DateTime.now().subtract(const Duration(days: 30)),
      lastDate: DateTime.now(),
      builder: (context, child) {
        return Theme(
          data: Theme.of(
            context,
          ).copyWith(colorScheme: ColorScheme.light(primary: widget.color)),
          child: child!,
        );
      },
    );

    if (date != null) {
      setState(() {
        _selectedDateTime = DateTime(
          date.year,
          date.month,
          date.day,
          _selectedDateTime.hour,
          _selectedDateTime.minute,
        );
      });
    }
  }

  Future<void> _selectTime() async {
    final time = await showTimePicker(
      context: context,
      initialTime: TimeOfDay.fromDateTime(_selectedDateTime),
      builder: (context, child) {
        return Theme(
          data: Theme.of(
            context,
          ).copyWith(colorScheme: ColorScheme.light(primary: widget.color)),
          child: child!,
        );
      },
    );

    if (time != null) {
      setState(() {
        _selectedDateTime = DateTime(
          _selectedDateTime.year,
          _selectedDateTime.month,
          _selectedDateTime.day,
          time.hour,
          time.minute,
        );
      });
    }
  }

  String _formatDate(DateTime date) {
    final months = [
      'Jan',
      'Feb',
      'Mar',
      'Apr',
      'May',
      'Jun',
      'Jul',
      'Aug',
      'Sep',
      'Oct',
      'Nov',
      'Dec',
    ];
    return '${months[date.month - 1]} ${date.day}, ${date.year}';
  }

  String _formatTime(DateTime time) {
    final hour = time.hour > 12
        ? time.hour - 12
        : (time.hour == 0 ? 12 : time.hour);
    final minute = time.minute.toString().padLeft(2, '0');
    final period = time.hour >= 12 ? 'PM' : 'AM';
    return '$hour:$minute $period';
  }

  Future<void> _handleSubmit() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() => _isSubmitting = true);

    final provider = context.read<VitalsProvider>();

    // Find vital type ID
    final vitalType = provider.vitalTypes.firstWhere(
      (vt) => vt.code == widget.vitalCode,
      orElse: () => provider.vitalTypes.first,
    );

    bool success;

    if (widget.vitalCode == 'BP') {
      success = await provider.createReading(
        vitalTypeId: vitalType.id,
        values: {
          'systolic': int.parse(_systolicController.text),
          'diastolic': int.parse(_diastolicController.text),
        },
        unit: 'mmHg',
        measuredAt: _selectedDateTime,
        notes: _notesController.text.isNotEmpty ? _notesController.text : null,
      );
    } else {
      success = await provider.createReading(
        vitalTypeId: vitalType.id,
        value: double.parse(_valueController.text),
        unit: _getUnit(),
        measuredAt: _selectedDateTime,
        notes: _notesController.text.isNotEmpty ? _notesController.text : null,
      );
    }

    setState(() => _isSubmitting = false);

    if (success && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Row(
            children: [
              Icon(Icons.check_circle, color: Colors.white),
              const SizedBox(width: 12),
              Text('Reading saved successfully'),
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
    } else if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(provider.error ?? 'Failed to save reading'),
          backgroundColor: AppColors.error,
        ),
      );
    }
  }
}
