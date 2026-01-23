import 'package:flutter/material.dart';
import '../models/device.dart';
import '../services/device_service.dart';

class DeviceProvider with ChangeNotifier {
  final DeviceService _service = DeviceService();

  List<DeviceStatus> _devices = [];
  bool _isLoading = false;
  String? _error;

  List<DeviceStatus> get devices => _devices;
  bool get isLoading => _isLoading;
  String? get error => _error;

  // Get connected devices
  List<DeviceStatus> get connectedDevices {
    return _devices.where((d) => d.isConnected).toList();
  }

  // Get devices with low battery
  List<DeviceStatus> get lowBatteryDevices {
    return _devices.where((d) => d.needsBattery).toList();
  }

  // Load device status
  Future<void> loadDevices() async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final results = await _service.getDeviceStatus();
      _devices = (results).map((i) => DeviceStatus.fromJson(i)).toList();
    } catch (e) {
      _error = e.toString();
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  // Refresh devices
  Future<void> refresh() async {
    await loadDevices();
  }

  // Clear error
  void clearError() {
    _error = null;
    notifyListeners();
  }
}
