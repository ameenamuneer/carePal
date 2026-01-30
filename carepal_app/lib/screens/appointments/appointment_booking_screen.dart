import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../providers/appointment_provider.dart';
import '../../models/appointment.dart';
import 'package:intl/intl.dart';

class AppointmentBookingScreen extends StatefulWidget {
  const AppointmentBookingScreen({super.key});

  @override
  _AppointmentBookingScreenState createState() =>
      _AppointmentBookingScreenState();
}

class _AppointmentBookingScreenState extends State<AppointmentBookingScreen> {
  // Mock data for demo - in real app would come from API
  final List<Map<String, String>> _doctors = [
    {
      'id': 'doc_1',
      'name': 'Dr. Sarah Smith',
      'specialty': 'Cardiologist',
      'clinic': 'Heart Care Clinic',
      'clinic_id': 'clinic_1',
    },
    {
      'id': 'doc_2',
      'name': 'Dr. John Doe',
      'specialty': 'General Physician',
      'clinic': 'City Health Center',
      'clinic_id': 'clinic_2',
    },
  ];

  String? _selectedDoctorId;
  DateTime _selectedDate = DateTime.now().add(const Duration(days: 1));
  List<dynamic> _availableSlots = [];
  int? _selectedSlotTime;

  @override
  void initState() {
    super.initState();
    // Pre-select first doctor
    _selectedDoctorId = _doctors[0]['id'];
    _fetchSlots();
  }

  void _fetchSlots() {
    // In a real app we'd call provider.getAvailableSlots
    // Here we'll simulate slots for demo
    setState(() {
      _availableSlots = [
        {
          'time': _selectedDate.millisecondsSinceEpoch ~/ 1000 + 3600 * 9,
          'label': '09:00 AM',
        },
        {
          'time': _selectedDate.millisecondsSinceEpoch ~/ 1000 + 3600 * 10,
          'label': '10:00 AM',
        },
        {
          'time': _selectedDate.millisecondsSinceEpoch ~/ 1000 + 3600 * 11,
          'label': '11:00 AM',
        },
        {
          'time': _selectedDate.millisecondsSinceEpoch ~/ 1000 + 3600 * 14,
          'label': '02:00 PM',
        },
        {
          'time': _selectedDate.millisecondsSinceEpoch ~/ 1000 + 3600 * 16,
          'label': '04:00 PM',
        },
      ];
      _selectedSlotTime = null;
    });
  }

  void _bookAppointment() async {
    if (_selectedDoctorId == null || _selectedSlotTime == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please select a doctor and time slot')),
      );
      return;
    }

    final doctor = _doctors.firstWhere((d) => d['id'] == _selectedDoctorId);
    final provider = Provider.of<AppointmentProvider>(context, listen: false);

    final success = await provider.bookAppointment(
      doctorId: doctor['id']!,
      clinicId: doctor['clinic_id']!,
      appointmentTime: _selectedSlotTime!,
      doctorName: doctor['name']!,
      clinicName: doctor['clinic']!,
    );

    if (success) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Appointment Booked Successfully!')),
      );
      Navigator.pop(context);
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Booking Failed: ${provider.error}')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final provider = Provider.of<AppointmentProvider>(context);

    return Scaffold(
      appBar: AppBar(title: const Text('Book Appointment')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Select Doctor',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            DropdownButtonFormField<String>(
              initialValue: _selectedDoctorId,
              items: _doctors
                  .map(
                    (d) => DropdownMenuItem(
                      value: d['id'],
                      child: Text('${d['name']} (${d['specialty']})'),
                    ),
                  )
                  .toList(),
              onChanged: (value) {
                setState(() {
                  _selectedDoctorId = value;
                  _fetchSlots();
                });
              },
              decoration: const InputDecoration(border: OutlineInputBorder()),
            ),

            const SizedBox(height: 24),
            const Text(
              'Select Date',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            CalendarDatePicker(
              initialDate: _selectedDate,
              firstDate: DateTime.now(),
              lastDate: DateTime.now().add(const Duration(days: 30)),
              onDateChanged: (date) {
                setState(() {
                  _selectedDate = date;
                  _fetchSlots();
                });
              },
            ),

            const SizedBox(height: 24),
            const Text(
              'Available Slots',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: _availableSlots.map((slot) {
                final isSelected = _selectedSlotTime == slot['time'];
                return ChoiceChip(
                  label: Text(slot['label']),
                  selected: isSelected,
                  onSelected: (selected) {
                    setState(() {
                      _selectedSlotTime = selected ? slot['time'] : null;
                    });
                  },
                );
              }).toList(),
            ),

            const SizedBox(height: 32),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: provider.isLoading ? null : _bookAppointment,
                style: ElevatedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: 16),
                ),
                child: provider.isLoading
                    ? const CircularProgressIndicator(color: Colors.white)
                    : const Text('Confirm Booking'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
