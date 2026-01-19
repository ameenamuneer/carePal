import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:intl/intl.dart';
import '../../core/app_colors.dart';
import '../../providers/vitals_provider.dart';
import '../../models/vital_reading.dart';
import '../../widgets/vital_chart.dart';
import '../../widgets/loading_shimmer.dart';
import '../../widgets/error_view.dart';
import 'manual_entry_screen.dart';

class VitalsDetailScreen extends StatefulWidget {
  final String vitalCode;
  final String vitalName;
  final Color color;
  final IconData icon;

  const VitalsDetailScreen({
    super.key,
    required this.vitalCode,
    required this.vitalName,
    required this.color,
    required this.icon,
  });

  @override
  State<VitalsDetailScreen> createState() => _VitalsDetailScreenState();
}

class _VitalsDetailScreenState extends State<VitalsDetailScreen> {
  int _selectedDays = 7;
  final List<int> _dayOptions = [7, 14, 30];

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    await context.read<VitalsProvider>().loadReadings(
      vitalType: widget.vitalCode,
      days: _selectedDays,
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: AppColors.surface,
        elevation: 0,
        leading: IconButton(
          icon: Icon(Icons.arrow_back, color: AppColors.textPrimary),
          onPressed: () => Navigator.pop(context),
        ),
        title: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: widget.color.withOpacity(0.1),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Icon(widget.icon, color: widget.color, size: 20),
            ),
            const SizedBox(width: 12),
            Text(
              widget.vitalName,
              style: TextStyle(
                color: AppColors.textPrimary,
                fontSize: 18,
                fontWeight: FontWeight.bold,
              ),
            ),
          ],
        ),
        actions: [
          IconButton(
            icon: Icon(Icons.add_circle_outline, color: AppColors.primary),
            onPressed: () => _navigateToManualEntry(),
          ),
        ],
      ),
      body: Consumer<VitalsProvider>(
        builder: (context, provider, _) {
          if (provider.isLoading && provider.readings.isEmpty) {
            return _buildLoadingState();
          }

          if (provider.error != null && provider.readings.isEmpty) {
            return ErrorView(message: provider.error!, onRetry: _loadData);
          }

          final readings = provider.getReadingsByType(widget.vitalCode);

          return RefreshIndicator(
            onRefresh: _loadData,
            color: AppColors.primary,
            child: SingleChildScrollView(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Stats Cards
                  _buildStatsCards(readings),
                  const SizedBox(height: 24),

                  // Time Period Filter
                  _buildTimePeriodFilter(),
                  const SizedBox(height: 24),

                  // Chart Section
                  Container(
                    padding: const EdgeInsets.all(20),
                    decoration: BoxDecoration(
                      color: AppColors.surface,
                      borderRadius: BorderRadius.circular(24),
                      border: Border.all(
                        color: widget.color.withOpacity(0.1),
                        width: 1,
                      ),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Trend',
                          style: Theme.of(context).textTheme.titleMedium
                              ?.copyWith(
                                fontWeight: FontWeight.bold,
                                color: AppColors.textPrimary,
                              ),
                        ),
                        const SizedBox(height: 16),
                        VitalChart(
                          readings: readings,
                          vitalCode: widget.vitalCode,
                          color: widget.color,
                        ),
                      ],
                    ),
                  ),

                  const SizedBox(height: 24),

                  // Readings List
                  _buildReadingsList(readings),
                ],
              ),
            ),
          );
        },
      ),
    );
  }

  Widget _buildLoadingState() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        children: [
          Row(
            children: [
              Expanded(child: LoadingShimmer(height: 100, borderRadius: 20)),
              const SizedBox(width: 16),
              Expanded(child: LoadingShimmer(height: 100, borderRadius: 20)),
            ],
          ),
          const SizedBox(height: 24),
          LoadingShimmer(height: 300, borderRadius: 24),
          const SizedBox(height: 24),
          LoadingShimmer(height: 200, borderRadius: 24),
        ],
      ),
    );
  }

  Widget _buildStatsCards(List<VitalReading> readings) {
    if (readings.isEmpty) {
      return Row(
        children: [
          Expanded(child: _buildStatCard('Latest', '--', '--')),
          const SizedBox(width: 16),
          Expanded(child: _buildStatCard('Average', '--', '--')),
        ],
      );
    }

    final latest = readings.first;
    final latestValue = latest.displayValue;
    final latestTime = DateFormat('MMM dd, hh:mm a').format(latest.measuredAt);

    // Calculate average
    double average = 0;
    if (widget.vitalCode == 'BP') {
      final systolicValues = readings
          .where((r) => r.values != null && r.values!['systolic'] != null)
          .map((r) => r.values!['systolic'].toDouble())
          .toList();
      average = systolicValues.isNotEmpty
          ? systolicValues.reduce((a, b) => a + b) / systolicValues.length
          : 0;
    } else {
      final values = readings
          .where((r) => r.value != null)
          .map((r) => r.value!)
          .toList();
      average = values.isNotEmpty
          ? values.reduce((a, b) => a + b) / values.length
          : 0;
    }

    return Row(
      children: [
        Expanded(child: _buildStatCard('Latest', latestValue, latestTime)),
        const SizedBox(width: 16),
        Expanded(
          child: _buildStatCard(
            'Average',
            average.toStringAsFixed(1),
            '$_selectedDays days',
          ),
        ),
      ],
    );
  }

  Widget _buildStatCard(String label, String value, String subtitle) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: widget.color.withOpacity(0.2), width: 1),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            style: TextStyle(
              fontSize: 13,
              color: AppColors.textSecondary,
              fontWeight: FontWeight.w500,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            value,
            style: TextStyle(
              fontSize: 24,
              fontWeight: FontWeight.bold,
              color: widget.color,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            subtitle,
            style: TextStyle(fontSize: 11, color: AppColors.textTertiary),
          ),
        ],
      ),
    );
  }

  Widget _buildTimePeriodFilter() {
    return Row(
      children: _dayOptions.map((days) {
        final isSelected = _selectedDays == days;
        return Expanded(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 4),
            child: GestureDetector(
              onTap: () {
                setState(() => _selectedDays = days);
                _loadData();
              },
              child: Container(
                padding: const EdgeInsets.symmetric(vertical: 12),
                decoration: BoxDecoration(
                  color: isSelected ? AppColors.primary : AppColors.surface,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(
                    color: isSelected ? AppColors.primary : AppColors.border,
                    width: 1.5,
                  ),
                ),
                child: Text(
                  '$days Days',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: isSelected ? Colors.white : AppColors.textSecondary,
                  ),
                ),
              ),
            ),
          ),
        );
      }).toList(),
    );
  }

  Widget _buildReadingsList(List<VitalReading> readings) {
    if (readings.isEmpty) {
      return Container(
        padding: const EdgeInsets.all(40),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(24),
        ),
        child: Column(
          children: [
            Icon(Icons.show_chart, size: 60, color: AppColors.textTertiary),
            const SizedBox(height: 16),
            Text(
              'No readings yet',
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w600,
                color: AppColors.textPrimary,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'Add your first reading to start tracking',
              style: TextStyle(fontSize: 14, color: AppColors.textSecondary),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      );
    }

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: AppColors.border, width: 1),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'Recent Readings',
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.bold,
                  color: AppColors.textPrimary,
                ),
              ),
              Text(
                '${readings.length} total',
                style: TextStyle(fontSize: 13, color: AppColors.textTertiary),
              ),
            ],
          ),
          const SizedBox(height: 16),
          ListView.separated(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            itemCount: readings.length > 10 ? 10 : readings.length,
            separatorBuilder: (_, __) =>
                Divider(height: 24, color: AppColors.divider),
            itemBuilder: (context, index) {
              final reading = readings[index];
              return _buildReadingItem(reading);
            },
          ),
        ],
      ),
    );
  }

  Widget _buildReadingItem(VitalReading reading) {
    final time = DateFormat('MMM dd, yyyy').format(reading.measuredAt);
    final timeOfDay = DateFormat('hh:mm a').format(reading.measuredAt);

    return Row(
      children: [
        Container(
          width: 48,
          height: 48,
          decoration: BoxDecoration(
            color: widget.color.withOpacity(0.1),
            borderRadius: BorderRadius.circular(12),
          ),
          child: Icon(widget.icon, color: widget.color, size: 24),
        ),
        const SizedBox(width: 16),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                reading.displayValue,
                style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                  color: AppColors.textPrimary,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                '$time • $timeOfDay',
                style: TextStyle(fontSize: 13, color: AppColors.textSecondary),
              ),
            ],
          ),
        ),
        if (reading.isAnomaly)
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            decoration: BoxDecoration(
              color: AppColors.warning.withOpacity(0.1),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Text(
              'Anomaly',
              style: TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w600,
                color: AppColors.warning,
              ),
            ),
          ),
      ],
    );
  }

  Future<void> _navigateToManualEntry() async {
    final result = await Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => ManualEntryScreen(
          vitalCode: widget.vitalCode,
          vitalName: widget.vitalName,
          color: widget.color,
        ),
      ),
    );

    if (result == true) {
      _loadData();
    }
  }
}
