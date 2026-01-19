import 'package:flutter/material.dart';
import 'package:fl_chart/fl_chart.dart';
import 'package:intl/intl.dart';
import '../core/app_colors.dart';
import '../models/vital_reading.dart';

class VitalChart extends StatelessWidget {
  final List<VitalReading> readings;
  final String vitalCode;
  final Color color;

  const VitalChart({
    super.key,
    required this.readings,
    required this.vitalCode,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    if (readings.isEmpty) {
      return Container(
        height: 250,
        alignment: Alignment.center,
        child: Text(
          'No data available',
          style: TextStyle(color: AppColors.textSecondary),
        ),
      );
    }

    // For Blood Pressure, show two lines (systolic/diastolic)
    if (vitalCode == 'BP') {
      return _buildBPChart();
    }

    // For other vitals, show single line
    return _buildSingleLineChart();
  }

  Widget _buildSingleLineChart() {
    final spots = readings.asMap().entries.map((entry) {
      final index = entry.key;
      final reading = entry.value;
      return FlSpot(index.toDouble(), reading.value ?? 0);
    }).toList();

    return Container(
      height: 250,
      padding: const EdgeInsets.all(16),
      child: LineChart(
        LineChartData(
          gridData: FlGridData(
            show: true,
            drawVerticalLine: false,
            horizontalInterval: 20,
            getDrawingHorizontalLine: (value) {
              return FlLine(color: AppColors.divider, strokeWidth: 1);
            },
          ),
          titlesData: FlTitlesData(
            leftTitles: AxisTitles(
              sideTitles: SideTitles(
                showTitles: true,
                reservedSize: 40,
                getTitlesWidget: (value, meta) {
                  return Text(
                    value.toInt().toString(),
                    style: TextStyle(
                      color: AppColors.textSecondary,
                      fontSize: 12,
                    ),
                  );
                },
              ),
            ),
            rightTitles: const AxisTitles(
              sideTitles: SideTitles(showTitles: false),
            ),
            topTitles: const AxisTitles(
              sideTitles: SideTitles(showTitles: false),
            ),
            bottomTitles: AxisTitles(
              sideTitles: SideTitles(
                showTitles: true,
                reservedSize: 30,
                getTitlesWidget: (value, meta) {
                  final index = value.toInt();
                  if (index < 0 || index >= readings.length) {
                    return const SizedBox();
                  }

                  final date = readings[index].measuredAt;
                  return Padding(
                    padding: const EdgeInsets.only(top: 8),
                    child: Text(
                      DateFormat('MM/dd').format(date),
                      style: TextStyle(
                        color: AppColors.textSecondary,
                        fontSize: 11,
                      ),
                    ),
                  );
                },
              ),
            ),
          ),
          borderData: FlBorderData(show: false),
          lineBarsData: [
            LineChartBarData(
              spots: spots,
              isCurved: true,
              color: color,
              barWidth: 3,
              dotData: FlDotData(
                show: true,
                getDotPainter: (spot, percent, barData, index) {
                  return FlDotCirclePainter(
                    radius: 4,
                    color: Colors.white,
                    strokeWidth: 2,
                    strokeColor: color,
                  );
                },
              ),
              belowBarData: BarAreaData(
                show: true,
                color: color.withOpacity(0.1),
              ),
            ),
          ],
          lineTouchData: LineTouchData(
            touchTooltipData: LineTouchTooltipData(
              getTooltipItems: (touchedSpots) {
                return touchedSpots.map((spot) {
                  final reading = readings[spot.x.toInt()];
                  return LineTooltipItem(
                    '${spot.y.toStringAsFixed(1)}\n${DateFormat('MMM dd, hh:mm a').format(reading.measuredAt)}',
                    const TextStyle(
                      color: Colors.white,
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                    ),
                  );
                }).toList();
              },
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildBPChart() {
    final systolicSpots = <FlSpot>[];
    final diastolicSpots = <FlSpot>[];

    for (var i = 0; i < readings.length; i++) {
      final reading = readings[i];
      if (reading.values != null) {
        final systolic = reading.values!['systolic']?.toDouble() ?? 0;
        final diastolic = reading.values!['diastolic']?.toDouble() ?? 0;
        systolicSpots.add(FlSpot(i.toDouble(), systolic));
        diastolicSpots.add(FlSpot(i.toDouble(), diastolic));
      }
    }

    return Container(
      height: 250,
      padding: const EdgeInsets.all(16),
      child: LineChart(
        LineChartData(
          gridData: FlGridData(
            show: true,
            drawVerticalLine: false,
            horizontalInterval: 20,
            getDrawingHorizontalLine: (value) {
              return FlLine(color: AppColors.divider, strokeWidth: 1);
            },
          ),
          titlesData: FlTitlesData(
            leftTitles: AxisTitles(
              sideTitles: SideTitles(
                showTitles: true,
                reservedSize: 40,
                getTitlesWidget: (value, meta) {
                  return Text(
                    value.toInt().toString(),
                    style: TextStyle(
                      color: AppColors.textSecondary,
                      fontSize: 12,
                    ),
                  );
                },
              ),
            ),
            rightTitles: const AxisTitles(
              sideTitles: SideTitles(showTitles: false),
            ),
            topTitles: const AxisTitles(
              sideTitles: SideTitles(showTitles: false),
            ),
            bottomTitles: AxisTitles(
              sideTitles: SideTitles(
                showTitles: true,
                reservedSize: 30,
                getTitlesWidget: (value, meta) {
                  final index = value.toInt();
                  if (index < 0 || index >= readings.length) {
                    return const SizedBox();
                  }

                  final date = readings[index].measuredAt;
                  return Padding(
                    padding: const EdgeInsets.only(top: 8),
                    child: Text(
                      DateFormat('MM/dd').format(date),
                      style: TextStyle(
                        color: AppColors.textSecondary,
                        fontSize: 11,
                      ),
                    ),
                  );
                },
              ),
            ),
          ),
          borderData: FlBorderData(show: false),
          lineBarsData: [
            // Systolic line
            LineChartBarData(
              spots: systolicSpots,
              isCurved: true,
              color: AppColors.vitalsRed,
              barWidth: 3,
              dotData: FlDotData(
                show: true,
                getDotPainter: (spot, percent, barData, index) {
                  return FlDotCirclePainter(
                    radius: 4,
                    color: Colors.white,
                    strokeWidth: 2,
                    strokeColor: AppColors.vitalsRed,
                  );
                },
              ),
              belowBarData: BarAreaData(
                show: true,
                color: AppColors.vitalsRed.withOpacity(0.1),
              ),
            ),
            // Diastolic line
            LineChartBarData(
              spots: diastolicSpots,
              isCurved: true,
              color: AppColors.primary,
              barWidth: 3,
              dotData: FlDotData(
                show: true,
                getDotPainter: (spot, percent, barData, index) {
                  return FlDotCirclePainter(
                    radius: 4,
                    color: Colors.white,
                    strokeWidth: 2,
                    strokeColor: AppColors.primary,
                  );
                },
              ),
              belowBarData: BarAreaData(
                show: true,
                color: AppColors.primary.withOpacity(0.1),
              ),
            ),
          ],
          lineTouchData: LineTouchData(
            touchTooltipData: LineTouchTooltipData(
              getTooltipItems: (touchedSpots) {
                if (touchedSpots.isEmpty) return [];
                final index = touchedSpots.first.x.toInt();
                final reading = readings[index];

                return [
                  LineTooltipItem(
                    'Sys: ${touchedSpots[0].y.toInt()}\nDia: ${touchedSpots.length > 1 ? touchedSpots[1].y.toInt() : '--'}\n${DateFormat('MMM dd, hh:mm a').format(reading.measuredAt)}',
                    const TextStyle(
                      color: Colors.white,
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ];
              },
            ),
          ),
        ),
      ),
    );
  }
}
