// lib/utils/dashboard_debug.dart
// DIAGNOSTIC TOOL - Check what dashboard API is returning

import 'package:flutter/material.dart';
import 'dart:convert';
import '../services/api_service.dart';
import '../services/dashboard_service.dart';

class DashboardDebugger {
  static Future<void> checkDashboardAPI(BuildContext context) async {
    final api = ApiService();
    final dashboardService = DashboardService();

    print('🔍 === DASHBOARD API DEBUGGING ===');

    // Test 1: Check Dashboard Endpoint Directly
    print('\n📊 Test 1: Checking Dashboard API Endpoint');
    print('URL: /api/v1/analytics/dashboard/patient/');

    try {
      final response = await api.get('/api/v1/analytics/dashboard/patient/');
      print('✅ Dashboard API Response:');
      print('Status: 200 OK');
      print('Data structure:');
      print(jsonEncode(response.data));

      // Check if vitals summary exists
      if (response.data['vitals_summary'] != null) {
        print('\n✅ vitals_summary found in response');
        print('Vitals Summary:');
        print(jsonEncode(response.data['vitals_summary']));
      } else if (response.data['vitalsSummary'] != null) {
        print('\n✅ vitalsSummary found in response');
        print('Vitals Summary:');
        print(jsonEncode(response.data['vitalsSummary']));
      } else {
        print('\n⚠️ WARNING: No vitals_summary or vitalsSummary in response!');
        print('Available keys: ${response.data.keys.toList()}');
      }
    } catch (e) {
      print('❌ ERROR calling dashboard API:');
      print(e.toString());

      if (e.toString().contains('404')) {
        print('\n🔍 404 Error - Endpoint not found!');
        print('Possible issues:');
        print('1. Backend route not configured');
        print('2. Analytics app not included in INSTALLED_APPS');
        print('3. URL path mismatch');
      } else if (e.toString().contains('500')) {
        print('\n🔍 500 Error - Server error!');
        print('Check Django logs for the actual error');
      } else if (e.toString().contains('403') || e.toString().contains('401')) {
        print('\n🔍 Auth Error!');
        print('Token might be expired or invalid');
      }
    }

    // Test 2: Try Loading via DashboardService
    print('\n📊 Test 2: Loading via DashboardService');
    try {
      final dashboardData = await dashboardService.getDashboard();
      print('✅ DashboardService loaded successfully');
      print('Has vitals summary: ${dashboardData.vitalsSummary != null}');
      print('Vitals in summary: ${dashboardData.vitalsSummary!.keys.toList()}');
    } catch (e) {
      print('❌ ERROR loading via DashboardService:');
      print(e.toString());
    }

    // Test 3: Check Vitals API directly (we know this works)
    print('\n📊 Test 3: Checking Vitals API (for comparison)');
    try {
      final vitalsResponse = await api.get(
        '/api/v1/vitals/readings/?page_size=5',
      );
      print(
        '✅ Vitals API works: ${vitalsResponse.data['count']} readings found',
      );
    } catch (e) {
      print('❌ Vitals API error: $e');
    }

    // Test 4: Check if backend has patient ID
    print('\n📊 Test 4: Checking Auth/Patient Info');
    try {
      final profileResponse = await api.get('/api/v1/auth/profile/');
      print('✅ Profile API Response:');
      print('User type: ${profileResponse.data['user_type']}');
      if (profileResponse.data['patient_profile'] != null) {
        print('Patient ID: ${profileResponse.data['patient_profile']['id']}');
      } else {
        print('⚠️ WARNING: No patient_profile in user data!');
      }
    } catch (e) {
      print('❌ Profile API error: $e');
    }

    print('\n🔍 === END DASHBOARD DEBUGGING ===\n');

    // Show result to user
    if (context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Dashboard debug complete - check console'),
          backgroundColor: Colors.blue,
          duration: Duration(seconds: 3),
        ),
      );
    }
  }

  /// Quick test button
  static Future<void> quickTest(BuildContext context) async {
    print('🚀 Quick Dashboard Test');

    final api = ApiService();

    try {
      // Just try to hit the endpoint
      final response = await api.get('/api/v1/analytics/dashboard/patient/');

      if (context.mounted) {
        showDialog(
          context: context,
          builder: (context) => AlertDialog(
            title: Text('Dashboard API Test'),
            content: SingleChildScrollView(
              child: Text(
                'Status: Success ✅\n\n'
                'Response Keys:\n${response.data.keys.join('\n')}\n\n'
                'Has vitals_summary: ${response.data.containsKey('vitals_summary')}\n'
                'Has vitalsSummary: ${response.data.containsKey('vitalsSummary')}',
              ),
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(context),
                child: Text('Close'),
              ),
            ],
          ),
        );
      }
    } catch (e) {
      if (context.mounted) {
        showDialog(
          context: context,
          builder: (context) => AlertDialog(
            title: Text('Dashboard API Test'),
            content: Text(
              'Status: Failed ❌\n\n'
              'Error: $e\n\n'
              'Check console for details.',
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(context),
                child: Text('Close'),
              ),
            ],
          ),
        );
      }
    }
  }
}

/// Debug FAB to add to Dashboard
class DashboardDebugFAB extends StatelessWidget {
  const DashboardDebugFAB({super.key});

  @override
  Widget build(BuildContext context) {
    return FloatingActionButton.extended(
      onPressed: () => DashboardDebugger.checkDashboardAPI(context),
      label: Text('Debug Dashboard'),
      icon: Icon(Icons.bug_report),
      backgroundColor: Colors.orange,
    );
  }
}
