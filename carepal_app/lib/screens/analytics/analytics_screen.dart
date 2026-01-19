import 'package:flutter/material.dart';
import 'package:fl_chart/fl_chart.dart';
import 'package:provider/provider.dart';
import '../../core/app_colors.dart';
import '../../providers/vitals_provider.dart';
import '../../providers/medication_provider.dart';

class AnalyticsScreen extends StatefulWidget {
  const AnalyticsScreen({super.key});

  @override
  State<AnalyticsScreen> createState() => _AnalyticsScreenState();
}

class _AnalyticsScreenState extends State<AnalyticsScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
          decoration: BoxDecoration(
            color: AppColors.surface,
            boxShadow: [
              BoxShadow(
                color: Colors.black.withOpacity(0.03),
                blurRadius: 10,
                offset: const Offset(0, 2),
              ),
            ],
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Analytics',
                style: TextStyle(
                  fontSize: 28,
                  fontWeight: FontWeight.bold,
                  color: AppColors.textPrimary,
                ),
              ),
              const SizedBox(height: 16),
              TabBar(
                controller: _tabController,
                labelColor: AppColors.primary,
                unselectedLabelColor: AppColors.textSecondary,
                indicatorColor: AppColors.primary,
                indicatorWeight: 3,
                labelStyle: const TextStyle(fontWeight: FontWeight.w600),
                tabs: const [
                  Tab(text: 'Vitals'),
                  Tab(text: 'Medications'),
                ],
              ),
            ],
          ),
        ),
        Expanded(
          child: TabBarView(
            controller: _tabController,
            children: const [_VitalsTab(), _MedicationsTab()],
          ),
        ),
      ],
    );
  }
}

class _VitalsTab extends StatelessWidget {
  const _VitalsTab();

  @override
  Widget build(BuildContext context) {
    return Consumer<VitalsProvider>(
      builder: (context, provider, _) {
        final readings = provider.readings;

        return SingleChildScrollView(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _buildSummaryCards(provider),
              const SizedBox(height: 24),
              _buildTrendChart(readings),
              const SizedBox(height: 24),
              _buildRecentReadings(readings),
            ],
          ),
        );
      },
    );
  }

  Widget _buildSummaryCards(VitalsProvider provider) {
    return Row(
      children: [
        Expanded(
          child: _buildStatCard(
            'Total Readings',
            '${provider.readings.length}',
            Icons.assessment,
            AppColors.primary,
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: _buildStatCard(
            'This Week',
            '${provider.readings.where((r) => r.measuredAt.isAfter(DateTime.now().subtract(const Duration(days: 7)))).length}',
            Icons.calendar_today,
            AppColors.success,
          ),
        ),
      ],
    );
  }

  Widget _buildStatCard(
    String label,
    String value,
    IconData icon,
    Color color,
  ) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: color.withOpacity(0.2)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: color.withOpacity(0.1),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Icon(icon, color: color, size: 20),
          ),
          const SizedBox(height: 12),
          Text(
            value,
            style: TextStyle(
              fontSize: 28,
              fontWeight: FontWeight.bold,
              color: AppColors.textPrimary,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            label,
            style: TextStyle(fontSize: 12, color: AppColors.textSecondary),
          ),
        ],
      ),
    );
  }

  Widget _buildTrendChart(List readings) {
    if (readings.isEmpty) {
      return Container(
        padding: const EdgeInsets.all(40),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: AppColors.border),
        ),
        child: Center(
          child: Text(
            'No data to display',
            style: TextStyle(color: AppColors.textSecondary),
          ),
        ),
      );
    }

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Vital Trends',
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.bold,
              color: AppColors.textPrimary,
            ),
          ),
          const SizedBox(height: 20),
          SizedBox(
            height: 200,
            child: LineChart(
              LineChartData(
                gridData: FlGridData(show: false),
                titlesData: FlTitlesData(show: false),
                borderData: FlBorderData(show: false),
                lineBarsData: [
                  LineChartBarData(
                    spots: List.generate(
                      readings.length > 7 ? 7 : readings.length,
                      (i) => FlSpot(
                        i.toDouble(),
                        (readings[i].value ?? 0).toDouble(),
                      ),
                    ),
                    isCurved: true,
                    color: AppColors.primary,
                    barWidth: 3,
                    dotData: const FlDotData(show: false),
                    belowBarData: BarAreaData(
                      show: true,
                      color: AppColors.primary.withOpacity(0.1),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildRecentReadings(List readings) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Recent Readings',
          style: TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.bold,
            color: AppColors.textPrimary,
          ),
        ),
        const SizedBox(height: 12),
        Container(
          decoration: BoxDecoration(
            color: AppColors.surface,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: AppColors.border),
          ),
          child: readings.isEmpty
              ? Padding(
                  padding: const EdgeInsets.all(40),
                  child: Center(
                    child: Text(
                      'No readings yet',
                      style: TextStyle(color: AppColors.textSecondary),
                    ),
                  ),
                )
              : ListView.separated(
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  itemCount: readings.length > 5 ? 5 : readings.length,
                  separatorBuilder: (_, __) =>
                      Divider(height: 1, color: AppColors.divider),
                  itemBuilder: (context, index) {
                    final reading = readings[index];
                    return ListTile(
                      leading: Container(
                        padding: const EdgeInsets.all(8),
                        decoration: BoxDecoration(
                          color: AppColors.primaryLighter,
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Icon(
                          Icons.favorite,
                          color: AppColors.primary,
                          size: 20,
                        ),
                      ),
                      title: Text(
                        reading.displayValue,
                        style: TextStyle(
                          fontWeight: FontWeight.w600,
                          color: AppColors.textPrimary,
                        ),
                      ),
                      subtitle: Text(
                        reading.measuredAt.toString().split('.')[0],
                        style: TextStyle(
                          fontSize: 12,
                          color: AppColors.textSecondary,
                        ),
                      ),
                    );
                  },
                ),
        ),
      ],
    );
  }
}

class _MedicationsTab extends StatelessWidget {
  const _MedicationsTab();

  @override
  Widget build(BuildContext context) {
    return Consumer<MedicationProvider>(
      builder: (context, provider, _) {
        final adherence = provider.adherenceRate;

        return SingleChildScrollView(
          padding: const EdgeInsets.all(20),
          child: Column(
            children: [
              _buildAdherenceCard(adherence),
              const SizedBox(height: 24),
              _buildAdherenceChart(adherence),
            ],
          ),
        );
      },
    );
  }

  Widget _buildAdherenceCard(double rate) {
    return Container(
      padding: const EdgeInsets.all(28),
      decoration: BoxDecoration(
        gradient: AppColors.primaryGradient,
        borderRadius: BorderRadius.circular(24),
        boxShadow: [
          BoxShadow(
            color: AppColors.primary.withOpacity(0.3),
            blurRadius: 20,
            offset: const Offset(0, 10),
          ),
        ],
      ),
      child: Column(
        children: [
          Text(
            'Adherence Rate',
            style: TextStyle(
              color: Colors.white.withOpacity(0.9),
              fontSize: 14,
            ),
          ),
          const SizedBox(height: 16),
          Text(
            '${rate.toInt()}%',
            style: const TextStyle(
              color: Colors.white,
              fontSize: 64,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 12),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            decoration: BoxDecoration(
              color: Colors.white.withOpacity(0.2),
              borderRadius: BorderRadius.circular(16),
            ),
            child: Text(
              rate >= 80
                  ? 'EXCELLENT'
                  : rate >= 60
                  ? 'GOOD'
                  : 'NEEDS IMPROVEMENT',
              style: const TextStyle(
                color: Colors.white,
                fontSize: 12,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildAdherenceChart(double rate) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '7-Day Overview',
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.bold,
              color: AppColors.textPrimary,
            ),
          ),
          const SizedBox(height: 20),
          SizedBox(
            height: 200,
            child: Center(
              child: Text(
                'Chart coming soon',
                style: TextStyle(color: AppColors.textSecondary),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
