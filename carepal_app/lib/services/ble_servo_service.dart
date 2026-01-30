import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:flutter_blue_plus/flutter_blue_plus.dart';

class BleServoService extends ChangeNotifier {
  static const String _serviceUuid = "4fafc201-1fb5-459e-8fcc-c5c9c331914b";
  static const String _charPositionUuid = "beb5483e-36e1-4688-b7f5-ea07361b26a8";
  static const String _charDeltaUuid = "82487627-2432-4148-9366-0775d78705f1";
  static const String _charMinUuid = "3c6f6261-30d8-4d57-8149-5f25712e5491";
  static const String _charMaxUuid = "b18d2777-7c15-4674-8849-0ec60d375225";

  BluetoothDevice? _device;
  BluetoothCharacteristic? _positionChar;
  BluetoothCharacteristic? _deltaChar;
  BluetoothCharacteristic? _minChar;
  BluetoothCharacteristic? _maxChar;

  StreamSubscription<List<ScanResult>>? _scanSubscription;
  StreamSubscription<BluetoothConnectionState>? _connectionSubscription;
  StreamSubscription<List<int>>? _positionSubscription;

  bool _isScanning = false;
  bool get isScanning => _isScanning;

  bool _isConnected = false;
  bool get isConnected => _isConnected;

  String _currentPosition = "--";
  String get currentPosition => _currentPosition;

  String _minPosition = "--";
  String get minPosition => _minPosition;

  String _maxPosition = "--";
  String get maxPosition => _maxPosition;
  
  // Log messages for the admin console
  final List<String> _logs = [];
  List<String> get logs => List.unmodifiable(_logs);

  BleServoService() {
    _init();
  }

  void _init() async {
    // Helper to start scanning if allowed, otherwise wait
    // We can't easily request permissions from here without context,
    // so we assume UI (Dashboard) requests them.
    // We retry scanning periodically if not permitted.
    _startScanning();
  }

  void _log(String message) {
    final timestamp = DateTime.now().toIso8601String().split('T').last.split('.').first;
    _logs.add("[$timestamp] $message");
    if (_logs.length > 100) _logs.removeAt(0);
    notifyListeners();
    print("[BleServoService] $message");
  }

  void _startScanning() async {
    if (_isConnected) return;
    
    // Safety: Stop any existing scan and cancel previous subscription
    await FlutterBluePlus.stopScan(); 
    await _scanSubscription?.cancel();
    _scanSubscription = null;

    _log("Starting scan (broad)...");
    _isScanning = true;
    notifyListeners();

    try {
      // Check if Bluetooth is supported/on
      if (await FlutterBluePlus.isSupported == false) { 
        _log("Bluetooth not supported");
        return;
      }
      
      // Listen to scan results
      _scanSubscription = FlutterBluePlus.scanResults.listen((results) {
        for (ScanResult r in results) {
          // Log what we find to help debug (comment out for noise reduction once working)
          // _log("Scanned: ${r.device.platformName}");

          // Check for Service UUID OR Name (fallback)
          if (r.advertisementData.serviceUuids.contains(_serviceUuid) || 
              r.device.platformName.contains("ESP32") || 
              r.device.platformName.toUpperCase().contains("SERVO")) {
             
             _log("Found Target: ${r.device.platformName} (${r.device.remoteId})");
             _connect(r.device);
             break; 
          }
        }
      });

      // Start scan - OPEN (no filters) 
      await FlutterBluePlus.startScan(
        timeout: const Duration(seconds: 15),
      );
    } catch (e) {
      _log("Error starting scan: $e");
      _isScanning = false;
      notifyListeners();
    }
  }

  Future<void> _connect(BluetoothDevice device) async {
    _log("Connecting to ${device.remoteId}...");
    await FlutterBluePlus.stopScan();
    _isScanning = false;
    notifyListeners();

    _device = device;

    _connectionSubscription = _device!.connectionState.listen((state) {
      _isConnected = state == BluetoothConnectionState.connected;
      _log("Connection state: $state");
      notifyListeners();
      
      if (state == BluetoothConnectionState.disconnected) {
        _cleanupConnection();
        _startScanning(); // Restart scanning on disconnect
      }
    });

    try {
      await _device!.connect();
      _log("Connected!");
      await _discoverServices();
    } catch (e) {
      _log("Connection error: $e");
      // _cleanupConnection called by listener on disconnect usually, 
      // but if connect throws, we might need to retry manually or let listener handle it
    }
  }

  Future<void> _discoverServices() async {
    if (_device == null) return;
    _log("Discovering services...");
    
    try {
      List<BluetoothService> services = await _device!.discoverServices();
      for (var service in services) {
        if (service.uuid.toString() == _serviceUuid) {
          for (var characteristic in service.characteristics) {
            String uuid = characteristic.uuid.toString();
            if (uuid == _charPositionUuid) {
              _positionChar = characteristic;
              _setupPositionNotifications();
              _readPosition();
            } else if (uuid == _charDeltaUuid) {
              _deltaChar = characteristic;
            } else if (uuid == _charMinUuid) {
              _minChar = characteristic;
              _readMin();
            } else if (uuid == _charMaxUuid) {
              _maxChar = characteristic;
              _readMax();
            }
          }
        }
      }
      _log("Services discovered & configured.");
    } catch (e) {
      _log("Service discovery failed: $e");
    }
  }

  void _setupPositionNotifications() async {
    if (_positionChar != null) {
      await _positionChar!.setNotifyValue(true);
      _positionSubscription = _positionChar!.lastValueStream.listen((value) {
        String pos = utf8.decode(value);
        _currentPosition = pos;
        _log("Position update: $pos");
        notifyListeners();
      });
    }
  }
  
  Future<void> _readPosition() async {
    if (_positionChar != null) {
      var value = await _positionChar!.read();
      _currentPosition = utf8.decode(value);
      notifyListeners();
    }
  }

  Future<void> _readMin() async {
    if (_minChar != null) {
      var value = await _minChar!.read();
      _minPosition = utf8.decode(value);
      notifyListeners();
    }
  }

  Future<void> _readMax() async {
    if (_maxChar != null) {
      var value = await _maxChar!.read();
      _maxPosition = utf8.decode(value);
      notifyListeners();
    }
  }

  Future<void> setPosition(String val) async {
    if (_positionChar == null) return;
    try {
      _log("Setting position: $val");
      await _positionChar!.write(utf8.encode(val));
    } catch (e) {
      _log("Error setting position: $e");
    }
  }

  Future<void> setDelta(String val) async {
    if (_deltaChar == null) return;
    try {
      _log("Setting delta: $val");
      await _deltaChar!.write(utf8.encode(val));
    } catch (e) {
      _log("Error setting delta: $e");
    }
  }

  Future<void> setMin(String val) async {
    if (_minChar == null) return;
    try {
      _log("Setting min: $val");
      await _minChar!.write(utf8.encode(val));
      // Read back to confirm
      await _readMin();
    } catch (e) {
      _log("Error setting min: $e");
    }
  }

  Future<void> setMax(String val) async {
    if (_maxChar == null) return;
    try {
      _log("Setting max: $val");
      await _maxChar!.write(utf8.encode(val));
      // Read back to confirm
      await _readMax();
    } catch (e) {
      _log("Error setting max: $e");
    }
  }

  void _cleanupConnection() {
    _positionSubscription?.cancel();
    _positionChar = null;
    _deltaChar = null;
    _minChar = null;
    _maxChar = null;
    // Don't nullify _device here immediately if we want to reconnect, 
    // but typically scanning starts fresh.
  }

  @override
  void dispose() {
    _scanSubscription?.cancel();
    _connectionSubscription?.cancel();
    _positionSubscription?.cancel();
    _device?.disconnect();
    super.dispose();
  }
}