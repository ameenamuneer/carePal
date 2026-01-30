import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:intl/intl.dart';
import '../../providers/appointment_provider.dart';
import '../../models/appointment.dart';
import 'appointment_booking_screen.dart';

class AppointmentListScreen extends StatefulWidget {
  const AppointmentListScreen({super.key});

  @override
  _AppointmentListScreenState createState() => _AppointmentListScreenState();
}

class _AppointmentListScreenState extends State<AppointmentListScreen> {
  @override
  void initState() {
    super.initState();
    Future.microtask(
      () => Provider.of<AppointmentProvider>(
        context,
        listen: false,
      ).loadAppointments(),
    );
  }

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 2,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('My Appointments'),
          bottom: const TabBar(
            tabs: [
              Tab(text: 'Upcoming'),
              Tab(text: 'Past'),
            ],
          ),
          actions: [
            IconButton(
              icon: const Icon(Icons.add),
              onPressed: () {
                Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (context) => const AppointmentBookingScreen(),
                  ),
                ).then((_) {
                  // Refresh list after booking
                  Provider.of<AppointmentProvider>(
                    context,
                    listen: false,
                  ).loadAppointments();
                });
              },
            ),
          ],
        ),
        body: Consumer<AppointmentProvider>(
          builder: (context, provider, child) {
            if (provider.isLoading) {
              return const Center(child: CircularProgressIndicator());
            }

            if (provider.error != null) {
              return Center(child: Text('Error: ${provider.error}'));
            }

            return TabBarView(
              children: [
                _buildAppointmentList(provider.upcomingAppointments),
                _buildAppointmentList(provider.pastAppointments),
              ],
            );
          },
        ),
      ),
    );
  }

  Widget _buildAppointmentList(List<Appointment> appointments) {
    if (appointments.isEmpty) {
      return const Center(child: Text('No appointments found'));
    }

    return ListView.builder(
      itemCount: appointments.length,
      itemBuilder: (context, index) {
        final appointment = appointments[index];
        return Card(
          margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          child: ListTile(
            leading: CircleAvatar(
              backgroundColor: appointment.isUpcoming
                  ? Colors.blue
                  : Colors.grey,
              child: Icon(Icons.calendar_today, color: Colors.white),
            ),
            title: Text(appointment.doctorName),
            subtitle: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('${appointment.clinicName} • ${appointment.mode}'),
                Text(
                  DateFormat(
                    'MMM dd, yyyy • hh:mm a',
                  ).format(appointment.appointmentDate),
                  style: const TextStyle(fontWeight: FontWeight.bold),
                ),
              ],
            ),
            trailing: Chip(
              label: Text(
                appointment.status,
                style: const TextStyle(fontSize: 10),
              ),
              backgroundColor: appointment.status == 'BOOKED'
                  ? Colors.green[100]
                  : Colors.grey[200],
            ),
          ),
        );
      },
    );
  }
}
