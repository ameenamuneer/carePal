class DeviceStatus {
  final int deviceId;
  final String deviceName;
  final String deviceType;
  final String sourceType;
  final bool isActive;
  final DateTime? lastSyncAt;
  final DateTime? lastReadingAt;
  final int? batteryLevel;
  final String connectionStatus;
  final int totalReadings;

  DeviceStatus({
    required this.deviceId,
    required this.deviceName,
    required this.deviceType,
    required this.sourceType,
    required this.isActive,
    this.lastSyncAt,
    this.lastReadingAt,
    this.batteryLevel,
    required this.connectionStatus,
    required this.totalReadings,
  });

  factory DeviceStatus.fromJson(Map<String, dynamic> json) {
    return DeviceStatus(
      deviceId: json['device_id'],
      deviceName: json['device_name'],
      deviceType: json['device_type'],
      sourceType: json['source_type'],
      isActive: json['is_active'],
      lastSyncAt: json['last_sync_at'] != null
          ? DateTime.parse(json['last_sync_at'])
          : null,
      lastReadingAt: json['last_reading_at'] != null
          ? DateTime.parse(json['last_reading_at'])
          : null,
      batteryLevel: json['battery_level'],
      connectionStatus: json['connection_status'],
      totalReadings: json['total_readings'],
    );
  }

  bool get isConnected => connectionStatus == 'connected';
  bool get needsBattery => batteryLevel != null && batteryLevel! < 20;
}
