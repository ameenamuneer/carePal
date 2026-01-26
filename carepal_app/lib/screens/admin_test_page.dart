import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/ble_servo_service.dart';
import '../core/app_colors.dart';

class AdminTestPage extends StatefulWidget {
  const AdminTestPage({super.key});

  @override
  State<AdminTestPage> createState() => _AdminTestPageState();
}

class _AdminTestPageState extends State<AdminTestPage> {
  final TextEditingController _posController = TextEditingController();
  final TextEditingController _minController = TextEditingController();
  final TextEditingController _maxController = TextEditingController();

  @override
  void dispose() {
    _posController.dispose();
    _minController.dispose();
    _maxController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Admin Test Panel'),
        backgroundColor: AppColors.background,
        elevation: 0,
        iconTheme: IconThemeData(color: AppColors.textPrimary),
        titleTextStyle: TextStyle(color: AppColors.textPrimary, fontSize: 20, fontWeight: FontWeight.bold),
      ),
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: Consumer<BleServoService>(
          builder: (context, service, child) {
            return Padding(
              padding: const EdgeInsets.all(16.0),
              child: ListView(
                children: [
                  _buildConnectionStatus(service),
                  const SizedBox(height: 20),
                  _buildPositionControl(service),
                  const SizedBox(height: 20),
                  _buildDeltaControl(service),
                  const SizedBox(height: 20),
                  _buildConfigControl(service),
                  const SizedBox(height: 20),
                  _buildLogs(service),
                ],
              ),
            );
          },
        ),
      ),
    );
  }

  Widget _buildConnectionStatus(BleServoService service) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: service.isConnected ? AppColors.success : AppColors.error,
          width: 2,
        ),
      ),
      child: Column(
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'Status: ${service.isConnected ? "CONNECTED" : service.isScanning ? "SCANNING..." : "DISCONNECTED"}',
                style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
              ),
              Icon(
                service.isConnected ? Icons.bluetooth_connected : Icons.bluetooth_disabled,
                color: service.isConnected ? AppColors.success : AppColors.error,
              ),
            ],
          ),
          if (!service.isConnected && !service.isScanning)
             TextButton(onPressed: (){}, child: Text("Scanning starts automatically in background"))
        ],
      ),
    );
  }

  Widget _buildPositionControl(BleServoService service) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text("Position Control", style: TextStyle(fontWeight: FontWeight.bold, fontSize: 18)),
            const SizedBox(height: 10),
            Row(
              children: [
                Expanded(
                  child: Text("Current Position: ${service.currentPosition}", style: const TextStyle(fontSize: 16)),
                ),
              ],
            ),
            const SizedBox(height: 10),
            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _posController,
                    decoration: const InputDecoration(labelText: "Set Position", border: OutlineInputBorder()),
                    keyboardType: TextInputType.number,
                  ),
                ),
                const SizedBox(width: 10),
                ElevatedButton(
                  onPressed: service.isConnected ? () {
                    service.setPosition(_posController.text);
                    _posController.clear();
                  } : null,
                  style: ElevatedButton.styleFrom(minimumSize: const Size(80, 48)), // Override global theme
                  child: const Text("Set"),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildDeltaControl(BleServoService service) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text("Delta Control", style: TextStyle(fontWeight: FontWeight.bold, fontSize: 18)),
            const SizedBox(height: 10),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceEvenly,
              children: [
                ElevatedButton(
                  onPressed: service.isConnected ? () => service.setDelta("-10") : null,
                  style: ElevatedButton.styleFrom(minimumSize: const Size(60, 48)),
                  child: const Text("-10"),
                ),
                ElevatedButton(
                  onPressed: service.isConnected ? () => service.setDelta("-1") : null,
                  style: ElevatedButton.styleFrom(minimumSize: const Size(60, 48)),
                  child: const Text("-1"),
                ),
                ElevatedButton(
                  onPressed: service.isConnected ? () => service.setDelta("1") : null,
                  style: ElevatedButton.styleFrom(minimumSize: const Size(60, 48)),
                  child: const Text("+1"),
                ),
                ElevatedButton(
                  onPressed: service.isConnected ? () => service.setDelta("10") : null,
                  style: ElevatedButton.styleFrom(minimumSize: const Size(60, 48)),
                  child: const Text("+10"),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildConfigControl(BleServoService service) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text("Configuration (Min/Max)", style: TextStyle(fontWeight: FontWeight.bold, fontSize: 18)),
            const SizedBox(height: 10),
            Row(
              children: [
                Expanded(child: Text("Min: ${service.minPosition}")),
                Expanded(child: Text("Max: ${service.maxPosition}")),
              ],
            ),
            const SizedBox(height: 10),
            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _minController,
                    decoration: const InputDecoration(labelText: "New Min", border: OutlineInputBorder()),
                    keyboardType: TextInputType.number,
                  ),
                ),
                const SizedBox(width: 5),
                ElevatedButton(
                  onPressed: service.isConnected ? () {
                    service.setMin(_minController.text);
                    _minController.clear();
                  } : null,
                  style: ElevatedButton.styleFrom(minimumSize: const Size(80, 48)),
                  child: const Text("Set"),
                ),
              ],
            ),
            const SizedBox(height: 10),
            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _maxController,
                    decoration: const InputDecoration(labelText: "New Max", border: OutlineInputBorder()),
                    keyboardType: TextInputType.number,
                  ),
                ),
                const SizedBox(width: 5),
                ElevatedButton(
                  onPressed: service.isConnected ? () {
                    service.setMax(_maxController.text);
                    _maxController.clear();
                  } : null,
                  style: ElevatedButton.styleFrom(minimumSize: const Size(80, 48)),
                  child: const Text("Set"),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
  
  Widget _buildLogs(BleServoService service) {
     return Container(
       height: 200,
       padding: const EdgeInsets.all(8),
       color: Colors.black12,
       child: ListView.builder(
         itemCount: service.logs.length,
         reverse: true, // Show newest at bottom if we were scrolling down, but usually logs are top-down. Let's start from end? 
         // Actually normally logs are reverse chronological or just appended. List is appended.
         // Let's reverse the list to show newest on top or just stick to bottom.
         // Let's just iterate reverse.
         itemBuilder: (context, index) {
            final log = service.logs[service.logs.length - 1 - index];
            return Text(log, style: const TextStyle(fontFamily: 'monospace', fontSize: 12));
         },
       ),
     );
  }
}
