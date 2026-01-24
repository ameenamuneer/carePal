// lib/utils/vitals_debug.dart
// DEBUG UTILITY - Test vitals API directly

import 'package:flutter/material.dart';
import 'dart:convert';
import '../services/api_service.dart';

class VitalsDebugger {
  static Future<void> testVitalsAPI({
    required int patientId,
    required BuildContext context,
  }) async {
    final api = ApiService();

    print('🔍 === VITALS API DEBUGGING ===');

    // Test 1: Get Vital Types
    print('\n📋 Test 1: Getting Vital Types');
    try {
      final typesResponse = await api.get('/api/v1/vitals/vital-types/');
      print('✅ Vital Types Response:');
      print(jsonEncode(typesResponse.data));

      final types = typesResponse.data['results'] as List;
      if (types.isEmpty) {
        print('⚠️ WARNING: No vital types found in database!');
        return;
      }

      final hrType = types.firstWhere(
        (t) => t['code'] == 'HR',
        orElse: () => null,
      );

      if (hrType == null) {
        print('⚠️ WARNING: HR vital type not found!');
        return;
      }

      print('✅ Found HR vital type: ${hrType['id']} - ${hrType['name']}');

      // Test 2: Create Heart Rate Reading
      print('\n💓 Test 2: Creating HR Reading');
      final now = DateTime.now().toUtc();
      final testData = {
        'patient': patientId,
        'vital_type': hrType['id'],
        'value': 75.0,
        'unit': 'bpm',
        'measured_at': now.toIso8601String(),
        'source': 'MANUAL',
      };

      print('📤 Request Data:');
      print(jsonEncode(testData));

      try {
        final createResponse = await api.post(
          '/api/v1/vitals/readings/',
          data: testData,
        );

        print('✅ SUCCESS! Reading created:');
        print(jsonEncode(createResponse.data));

        if (context.mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('✅ API Test Successful!'),
              backgroundColor: Colors.green,
            ),
          );
        }
      } catch (e) {
        print('❌ ERROR Creating Reading:');
        print(e.toString());

        if (e.toString().contains('400')) {
          print('\n🔍 400 Bad Request - Possible Issues:');
          print('1. Check if patient_id=$patientId exists');
          print('2. Check if vital_type_id=${hrType['id']} exists');
          print('3. Verify unit "bpm" is valid for HR');
          print('4. Check date format: ${now.toIso8601String()}');
          print('5. Verify backend serializer requirements');
        }

        if (context.mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('❌ API Test Failed: $e'),
              backgroundColor: Colors.red,
            ),
          );
        }
      }
    } catch (e) {
      print('❌ ERROR in test:');
      print(e.toString());
    }

    print('\n🔍 === END DEBUGGING ===\n');
  }

  /// Test all vital types
  static Future<void> testAllVitals({
    required int patientId,
    required BuildContext context,
  }) async {
    final api = ApiService();

    print('🔍 === TESTING ALL VITAL TYPES ===');

    // Get vital types
    final typesResponse = await api.get('/api/v1/vitals/vital-types/');
    final types = typesResponse.data['results'] as List;

    final testCases = [
      {'code': 'HR', 'value': 75.0, 'unit': 'bpm'},
      {'code': 'TEMP', 'value': 98.6, 'unit': '°F'},
      {'code': 'SPO2', 'value': 98.0, 'unit': '%'},
      {
        'code': 'BP',
        'values': {'systolic': 120, 'diastolic': 80},
        'unit': 'mmHg',
      },
    ];

    int passed = 0;
    int failed = 0;

    for (final testCase in testCases) {
      final code = testCase['code'] as String;
      print('\n📊 Testing $code...');

      try {
        final vitalType = types.firstWhere(
          (t) => t['code'] == code,
          orElse: () => null,
        );

        if (vitalType == null) {
          print('⚠️ Vital type $code not found');
          failed++;
          continue;
        }

        final data = <String, dynamic>{
          'patient': patientId,
          'vital_type': vitalType['id'],
          'unit': testCase['unit'],
          'measured_at': DateTime.now().toUtc().toIso8601String(),
          'source': 'MANUAL',
        };

        if (testCase.containsKey('value')) {
          data['value'] = testCase['value'];
        } else if (testCase.containsKey('values')) {
          data['values'] = testCase['values'];
        }

        print('📤 Request: ${jsonEncode(data)}');

        final response = await api.post('/api/v1/vitals/readings/', data: data);

        print('✅ $code: SUCCESS');
        passed++;
      } catch (e) {
        print('❌ $code: FAILED - $e');
        failed++;
      }
    }

    print('\n📊 === TEST SUMMARY ===');
    print('✅ Passed: $passed');
    print('❌ Failed: $failed');
    print('Total: ${passed + failed}');

    if (context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Tests Complete: $passed passed, $failed failed'),
          backgroundColor: failed == 0 ? Colors.green : Colors.orange,
        ),
      );
    }
  }
}

/// Debug Button Widget - Add to your UI for testing
class VitalsDebugButton extends StatelessWidget {
  final int patientId;

  const VitalsDebugButton({super.key, required this.patientId});

  @override
  Widget build(BuildContext context) {
    return FloatingActionButton.extended(
      onPressed: () =>
          VitalsDebugger.testVitalsAPI(patientId: patientId, context: context),
      label: Text('Debug API'),
      icon: Icon(Icons.bug_report),
      backgroundColor: Colors.orange,
    );
  }
}
