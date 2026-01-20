import 'dart:io';

void main() {
  print('🔍 Frontend Health Check\n');
  print('=' * 60);

  // Check required files exist
  final requiredFiles = [
    'lib/main.dart',
    'lib/core/app_colors.dart',
    'lib/services/api_service.dart',
    'lib/providers/auth_provider.dart',
    'lib/providers/dashboard_provider.dart',
    'lib/screens/login_screen.dart',
    'lib/screens/dashboard_screen.dart',
    'lib/models/dashboard_data.dart',
    'lib/services/medication_service.dart',
    'lib/services/emergency_service.dart',
  ];

  print('📁 Checking required files...');

  var allFound = true;
  for (final file in requiredFiles) {
    if (File(file).existsSync()) {
      print('✅ Found: $file');
    } else {
      print('❌ Missing: $file');
      allFound = false;
    }
  }

  if (allFound) {
    print('\n✅ Frontend structure looks good!');
  } else {
    print('\n⚠️ Some files are missing!');
  }
  print('=' * 60);
}
