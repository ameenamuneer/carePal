import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';
import 'package:fl_chart/fl_chart.dart';
import '../core/app_colors.dart';
import '../providers/auth_provider.dart';
import '../providers/patient_provider.dart';
import '../providers/dashboard_provider.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  void _load({bool force = false}) {
    final patient = context.read<PatientProvider>();
    final auth = context.read<AuthProvider>();
    final dash = context.read<DashboardProvider>();
    if (patient.activePatientId != null) {
      dash.load(
        patientId: patient.activePatientId!,
        isDoctor: auth.isDoctor,
        force: force,
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final patient = context.watch<PatientProvider>();
    final auth = context.watch<AuthProvider>();

    // Reload when patient changes
    context.select<PatientProvider, int?>((p) => p.activePatientId);

    if (patient.activePatientId == null) {
      return const _NoPatientState();
    }

    return RefreshIndicator(
      color: AppColors.primary,
      onRefresh: () async => _load(force: true),
      child: auth.isDoctor
          ? const _DoctorDashboard()
          : const _FamilyDashboard(),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// No Patient State
// ─────────────────────────────────────────────────────────────────────────────

class _NoPatientState extends StatelessWidget {
  const _NoPatientState();

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Container(
                width: 80,
                height: 80,
                decoration: BoxDecoration(
                  color: AppColors.primaryLighter,
                  borderRadius: BorderRadius.circular(20),
                ),
                child: const Icon(Icons.person_search,
                    size: 40, color: AppColors.primary),
              ),
              const SizedBox(height: 20),
              Text('No Patient Selected',
                  style: GoogleFonts.lexend(
                      fontSize: 20,
                      fontWeight: FontWeight.bold,
                      color: AppColors.textPrimary)),
              const SizedBox(height: 8),
              Text('Select a patient from the bar above\nor link a new patient to get started.',
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                      color: AppColors.textSecondary, fontSize: 14)),
            ],
          ),
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Shared scaffold that wraps both dashboards
// ─────────────────────────────────────────────────────────────────────────────

class _DashboardShell extends StatelessWidget {
  final String roleLabel;
  final String patientName;
  final Widget child;
  final VoidCallback onRefresh;

  const _DashboardShell({
    required this.roleLabel,
    required this.patientName,
    required this.child,
    required this.onRefresh,
  });

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: Column(
          children: [
            // ── Header ──────────────────────────────────────────────────────
            Container(
              width: double.infinity,
              padding: const EdgeInsets.fromLTRB(20, 20, 20, 20),
              decoration: const BoxDecoration(
                gradient: AppColors.primaryGradient,
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('Viewing Patient',
                            style: GoogleFonts.lexend(
                                fontSize: 12,
                                color: Colors.white.withOpacity(0.7))),
                        const SizedBox(height: 2),
                        Text(patientName,
                            style: GoogleFonts.lexend(
                                fontSize: 22,
                                fontWeight: FontWeight.bold,
                                color: Colors.white)),
                        const SizedBox(height: 10),
                        Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 10, vertical: 3),
                          decoration: BoxDecoration(
                            color: Colors.white.withOpacity(0.18),
                            borderRadius: BorderRadius.circular(20),
                          ),
                          child: Text(roleLabel,
                              style: GoogleFonts.lexend(
                                  fontSize: 10,
                                  fontWeight: FontWeight.w700,
                                  color: Colors.white,
                                  letterSpacing: 1.2)),
                        ),
                      ],
                    ),
                  ),
                  IconButton(
                    icon: const Icon(Icons.refresh, color: Colors.white),
                    onPressed: onRefresh,
                  ),
                ],
              ),
            ),
            // ── Body ────────────────────────────────────────────────────────
            Expanded(child: child),
          ],
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// FAMILY DASHBOARD
// ─────────────────────────────────────────────────────────────────────────────

class _FamilyDashboard extends StatelessWidget {
  const _FamilyDashboard();

  @override
  Widget build(BuildContext context) {
    final dash = context.watch<DashboardProvider>();
    final patient = context.watch<PatientProvider>();

    return _DashboardShell(
      roleLabel: 'FAMILY MEMBER',
      patientName: patient.activePatientName ?? '',
      onRefresh: () => context.read<DashboardProvider>().load(
            patientId: patient.activePatientId!,
            isDoctor: false,
            force: true,
          ),
      child: dash.isLoading && !dash.hasData
          ? const Center(child: CircularProgressIndicator(color: AppColors.primary))
          : dash.error != null && !dash.hasData
              ? _ErrorState(
                  message: dash.error!,
                  onRetry: () => context.read<DashboardProvider>().load(
                        patientId: patient.activePatientId!,
                        isDoctor: false,
                        force: true,
                      ))
              : ListView(
                  padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
                  children: [
                    // Alerts banner (critical/warning)
                    if ((dash.alertCounts['critical'] ?? 0) > 0 ||
                        (dash.alertCounts['warning'] ?? 0) > 0)
                      _AlertBanner(alertCounts: dash.alertCounts),

                    const SizedBox(height: 4),

                    // Medications card
                    _FamilyMedicationCard(
                      meds: dash.medications,
                      aiInsight: dash.aiInsight('medications'),
                    ),
                    const SizedBox(height: 12),

                    // Nutrition card
                    _FamilyNutritionCard(
                      nut: dash.nutrition,
                      aiInsight: dash.aiInsight('nutrition'),
                    ),
                    const SizedBox(height: 12),

                    // Mood card (if available)
                    if (dash.mood != null || dash.aiInsight('mood') != null) ...[
                      _FamilyMoodCard(
                        mood: dash.mood,
                        aiInsight: dash.aiInsight('mood'),
                      ),
                      const SizedBox(height: 12),
                    ],

                    // Vitals snapshot
                    if (dash.vitals.isNotEmpty || dash.aiInsight('vitals') != null) ...[
                      _FamilyVitalsCard(
                        vitals: dash.vitals,
                        aiInsight: dash.aiInsight('vitals'),
                      ),
                      const SizedBox(height: 12),
                    ],

                    // Recent activity
                    if (dash.recentActivity.isNotEmpty || dash.aiInsight('activity') != null)
                      _FamilyActivityCard(
                        activity: dash.recentActivity,
                        aiInsight: dash.aiInsight('activity'),
                      ),
                  ],
                ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// DOCTOR DASHBOARD
// ─────────────────────────────────────────────────────────────────────────────

class _DoctorDashboard extends StatelessWidget {
  const _DoctorDashboard();

  @override
  Widget build(BuildContext context) {
    final dash = context.watch<DashboardProvider>();
    final patient = context.watch<PatientProvider>();

    return _DashboardShell(
      roleLabel: 'DOCTOR',
      patientName: patient.activePatientName ?? '',
      onRefresh: () => context.read<DashboardProvider>().load(
            patientId: patient.activePatientId!,
            isDoctor: true,
            force: true,
          ),
      child: dash.isLoading && !dash.hasData
          ? const Center(child: CircularProgressIndicator(color: AppColors.primary))
          : dash.error != null && !dash.hasData
              ? _ErrorState(
                  message: dash.error!,
                  onRetry: () => context.read<DashboardProvider>().load(
                        patientId: patient.activePatientId!,
                        isDoctor: true,
                        force: true,
                      ))
              : ListView(
                  padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
                  children: [
                    // Active alerts
                    if (dash.alerts.isNotEmpty) ...[
                      _DoctorAlertsCard(alerts: dash.alerts),
                      const SizedBox(height: 12),
                    ],

                    // Medication overview + 7-day chart
                    _DoctorMedicationCard(
                      meds: dash.medications,
                      adherence7day: dash.adherence7day,
                    ),
                    const SizedBox(height: 12),

                    // Nutrition overview + 7-day chart
                    _DoctorNutritionCard(
                      nut: dash.nutrition,
                      nutrition7day: dash.nutrition7day,
                    ),
                    const SizedBox(height: 12),

                    // Vitals
                    if (dash.vitals.isNotEmpty) ...[
                      _DoctorVitalsCard(vitals: dash.vitals),
                      const SizedBox(height: 12),
                    ],

                    // Missed medications today
                    if (dash.missedToday.isNotEmpty) ...[
                      _MissedMedsCard(missed: dash.missedToday),
                      const SizedBox(height: 12),
                    ],
                  ],
                ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// SHARED WIDGETS
// ─────────────────────────────────────────────────────────────────────────────

class _SectionCard extends StatelessWidget {
  final String title;
  final IconData icon;
  final Color iconColor;
  final List<Widget> children;

  const _SectionCard({
    required this.title,
    required this.icon,
    required this.iconColor,
    required this.children,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.border),
        boxShadow: [
          BoxShadow(
            color: AppColors.shadowLight,
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 14, 16, 0),
            child: Row(
              children: [
                Container(
                  width: 32,
                  height: 32,
                  decoration: BoxDecoration(
                    color: iconColor.withOpacity(0.12),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Icon(icon, size: 18, color: iconColor),
                ),
                const SizedBox(width: 10),
                Text(title,
                    style: GoogleFonts.lexend(
                        fontSize: 14,
                        fontWeight: FontWeight.w600,
                        color: AppColors.textPrimary)),
              ],
            ),
          ),
          const SizedBox(height: 12),
          ...children,
          const SizedBox(height: 4),
        ],
      ),
    );
  }
}

class _StatRow extends StatelessWidget {
  final String label;
  final String value;
  final Color? valueColor;

  const _StatRow({required this.label, required this.value, this.valueColor});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 5),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label,
              style: const TextStyle(
                  fontSize: 13, color: AppColors.textSecondary)),
          Text(value,
              style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  color: valueColor ?? AppColors.textPrimary)),
        ],
      ),
    );
  }
}

class _Divider extends StatelessWidget {
  const _Divider();
  @override
  Widget build(BuildContext context) =>
      const Divider(color: AppColors.divider, height: 1, indent: 16, endIndent: 16);
}

class _ErrorState extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;
  const _ErrorState({required this.message, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.cloud_off, size: 48, color: AppColors.textTertiary),
            const SizedBox(height: 16),
            Text('Could not load dashboard',
                style: GoogleFonts.lexend(
                    fontSize: 16,
                    fontWeight: FontWeight.w600,
                    color: AppColors.textSecondary)),
            const SizedBox(height: 8),
            Text(message,
                textAlign: TextAlign.center,
                style: const TextStyle(
                    fontSize: 12, color: AppColors.textTertiary)),
            const SizedBox(height: 20),
            ElevatedButton.icon(
              onPressed: onRetry,
              icon: const Icon(Icons.refresh, size: 16),
              label: const Text('Retry'),
              style: ElevatedButton.styleFrom(backgroundColor: AppColors.primary),
            ),
          ],
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// AI Insight Badge — shown at the top of every family card
// ─────────────────────────────────────────────────────────────────────────────

class _AiInsightBadge extends StatelessWidget {
  final String text;
  final Color? accentColor;

  const _AiInsightBadge({required this.text, this.accentColor});

  @override
  Widget build(BuildContext context) {
    final color = accentColor ?? AppColors.primary;
    return Container(
      margin: const EdgeInsets.fromLTRB(16, 0, 16, 12),
      padding: const EdgeInsets.fromLTRB(12, 10, 12, 10),
      decoration: BoxDecoration(
        color: color.withOpacity(0.07),
        borderRadius: BorderRadius.circular(10),
        border: Border(left: BorderSide(color: color, width: 3)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(Icons.auto_awesome, size: 15, color: color),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              text,
              style: TextStyle(
                fontSize: 13.5,
                height: 1.45,
                color: AppColors.textPrimary,
                fontStyle: FontStyle.normal,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

// Alert banner (top of family dashboard)
class _AlertBanner extends StatelessWidget {
  final Map<String, dynamic> alertCounts;
  const _AlertBanner({required this.alertCounts});

  @override
  Widget build(BuildContext context) {
    final critical = (alertCounts['critical'] ?? 0) as int;
    final warning = (alertCounts['warning'] ?? 0) as int;
    final isCritical = critical > 0;
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        color: isCritical
            ? AppColors.error.withOpacity(0.10)
            : AppColors.warning.withOpacity(0.10),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: isCritical ? AppColors.error : AppColors.warning,
          width: 1.2,
        ),
      ),
      child: Row(
        children: [
          Icon(
            isCritical ? Icons.warning_amber_rounded : Icons.info_outline,
            color: isCritical ? AppColors.error : AppColors.warning,
            size: 22,
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              isCritical
                  ? '$critical critical alert${critical > 1 ? 's' : ''} need attention'
                  : '$warning health alert${warning > 1 ? 's' : ''} — review recommended',
              style: TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w600,
                color: isCritical ? AppColors.error : AppColors.warning,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// FAMILY CARDS
// ─────────────────────────────────────────────────────────────────────────────

class _FamilyMedicationCard extends StatelessWidget {
  final Map<String, dynamic> meds;
  final String? aiInsight;
  const _FamilyMedicationCard({required this.meds, this.aiInsight});

  @override
  Widget build(BuildContext context) {
    final status = meds['status'] as String? ?? 'none';
    final taken = meds['today_taken'] as int? ?? 0;
    final total = meds['today_total'] as int? ?? 0;

    Color statusColor;
    IconData statusIcon;
    switch (status) {
      case 'good':
        statusColor = AppColors.success;
        statusIcon = Icons.check_circle_outline;
        break;
      case 'partial':
        statusColor = AppColors.warning;
        statusIcon = Icons.radio_button_unchecked;
        break;
      case 'bad':
        statusColor = AppColors.error;
        statusIcon = Icons.cancel_outlined;
        break;
      default:
        statusColor = AppColors.textTertiary;
        statusIcon = Icons.medication_outlined;
    }

    return _SectionCard(
      title: 'Medications',
      icon: Icons.medication_outlined,
      iconColor: AppColors.primary,
      children: [
        // AI insight at the top
        if (aiInsight != null) _AiInsightBadge(text: aiInsight!, accentColor: statusColor),

        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: Row(
            children: [
              SizedBox(
                width: 72,
                height: 72,
                child: Stack(
                  alignment: Alignment.center,
                  children: [
                    CircularProgressIndicator(
                      value: total > 0 ? taken / total : 0,
                      strokeWidth: 7,
                      backgroundColor: AppColors.border,
                      color: statusColor,
                    ),
                    Text(
                      total > 0 ? '$taken/$total' : '—',
                      style: GoogleFonts.lexend(
                          fontSize: 14,
                          fontWeight: FontWeight.bold,
                          color: AppColors.textPrimary),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 16),
              Row(
                children: [
                  Icon(statusIcon, size: 16, color: statusColor),
                  const SizedBox(width: 4),
                  Text(
                    status == 'good'
                        ? 'All taken'
                        : status == 'partial'
                            ? 'Partially taken'
                            : status == 'bad'
                                ? 'None taken yet'
                                : 'No medications',
                    style: TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w600,
                        color: statusColor),
                  ),
                ],
              ),
            ],
          ),
        ),
        const SizedBox(height: 8),
      ],
    );
  }
}

class _FamilyNutritionCard extends StatelessWidget {
  final Map<String, dynamic> nut;
  final String? aiInsight;
  const _FamilyNutritionCard({required this.nut, this.aiInsight});

  @override
  Widget build(BuildContext context) {
    final status = nut['status'] as String? ?? 'none';
    final kcal = nut['today_kcal'] as int? ?? 0;
    final target = nut['daily_target'] as int?;
    final percent = nut['today_percent'] as int?;
    final mealCount = nut['meal_count'] as int? ?? 0;

    Color barColor;
    switch (status) {
      case 'good':
        barColor = AppColors.success;
        break;
      case 'low':
        barColor = AppColors.warning;
        break;
      case 'none':
        barColor = AppColors.textTertiary;
        break;
      default:
        barColor = Colors.orange;
    }

    return _SectionCard(
      title: 'Nutrition',
      icon: Icons.restaurant_outlined,
      iconColor: Colors.orange,
      children: [
        // AI insight at the top
        if (aiInsight != null) _AiInsightBadge(text: aiInsight!, accentColor: Colors.orange),

        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (target != null) ...[
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text('$kcal kcal',
                        style: GoogleFonts.lexend(
                            fontSize: 15,
                            fontWeight: FontWeight.bold,
                            color: AppColors.textPrimary)),
                    Text('of $target kcal target',
                        style: const TextStyle(
                            fontSize: 12, color: AppColors.textSecondary)),
                  ],
                ),
                const SizedBox(height: 8),
                ClipRRect(
                  borderRadius: BorderRadius.circular(4),
                  child: LinearProgressIndicator(
                    value: ((percent ?? 0) / 100).clamp(0.0, 1.0),
                    minHeight: 8,
                    backgroundColor: AppColors.border,
                    color: barColor,
                  ),
                ),
                const SizedBox(height: 4),
                Text('${percent ?? 0}% of daily goal · $mealCount meal${mealCount != 1 ? 's' : ''} logged',
                    style: const TextStyle(
                        fontSize: 11, color: AppColors.textSecondary)),
              ] else
                Text('$kcal kcal across $mealCount meal${mealCount != 1 ? 's' : ''} today',
                    style: GoogleFonts.lexend(
                        fontSize: 15,
                        fontWeight: FontWeight.bold,
                        color: AppColors.textPrimary)),
            ],
          ),
        ),
        const SizedBox(height: 8),
      ],
    );
  }
}

class _FamilyMoodCard extends StatelessWidget {
  final Map<String, dynamic>? mood;
  final String? aiInsight;
  const _FamilyMoodCard({this.mood, this.aiInsight});

  String _moodEmoji(dynamic score) {
    final s = (score as num?)?.toInt() ?? 5;
    if (s >= 8) return '😊';
    if (s >= 6) return '🙂';
    if (s >= 4) return '😐';
    if (s >= 2) return '😕';
    return '😞';
  }

  @override
  Widget build(BuildContext context) {
    final label = mood?['label'] as String? ?? '';
    final score = mood?['score'];
    return _SectionCard(
      title: 'Mood',
      icon: Icons.sentiment_satisfied_alt_outlined,
      iconColor: Colors.purple,
      children: [
        // AI insight at the top
        if (aiInsight != null) _AiInsightBadge(text: aiInsight!, accentColor: Colors.purple),

        if (mood != null)
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Row(
              children: [
                Text(_moodEmoji(score), style: const TextStyle(fontSize: 36)),
                const SizedBox(width: 14),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    if (label.isNotEmpty)
                      Text(label,
                          style: GoogleFonts.lexend(
                              fontSize: 16,
                              fontWeight: FontWeight.w600,
                              color: AppColors.textPrimary)),
                    if (score != null)
                      Text('Score: $score / 10',
                          style: const TextStyle(
                              fontSize: 12, color: AppColors.textSecondary)),
                  ],
                ),
              ],
            ),
          ),
        const SizedBox(height: 8),
      ],
    );
  }
}

class _FamilyVitalsCard extends StatelessWidget {
  final List<Map<String, dynamic>> vitals;
  final String? aiInsight;
  const _FamilyVitalsCard({required this.vitals, this.aiInsight});

  @override
  Widget build(BuildContext context) {
    final hasAnomaly = vitals.any((v) => v['is_anomaly'] == true);
    return _SectionCard(
      title: 'Latest Vitals',
      icon: Icons.monitor_heart_outlined,
      iconColor: hasAnomaly ? AppColors.error : AppColors.primary,
      children: [
        // AI insight at the top
        if (aiInsight != null)
          _AiInsightBadge(
            text: aiInsight!,
            accentColor: hasAnomaly ? AppColors.error : AppColors.primary,
          ),

        ...vitals.take(4).map((v) => Column(
              children: [
                _StatRow(
                  label: v['type_name'] as String? ?? '',
                  value: '${v['value']} ${v['unit'] ?? ''}'.trim(),
                  valueColor: (v['is_anomaly'] == true) ? AppColors.error : null,
                ),
              ],
            )),
      ],
    );
  }
}

class _FamilyActivityCard extends StatelessWidget {
  final List<Map<String, dynamic>> activity;
  final String? aiInsight;
  const _FamilyActivityCard({required this.activity, this.aiInsight});

  String _typeLabel(String type) {
    switch (type) {
      case 'MEAL':
        return '🍽️ Meal';
      case 'EXERCISE':
        return '🏃 Exercise';
      case 'SLEEP':
        return '😴 Sleep';
      case 'MOOD':
        return '💭 Mood';
      case 'MEDICATION':
        return '💊 Medication';
      default:
        return '📝 Activity';
    }
  }

  @override
  Widget build(BuildContext context) {
    return _SectionCard(
      title: 'Recent Activity',
      icon: Icons.history,
      iconColor: AppColors.info,
      children: [
        // AI insight at the top
        if (aiInsight != null) _AiInsightBadge(text: aiInsight!, accentColor: AppColors.info),

        ...activity.map((a) => Padding(
              padding: const EdgeInsets.fromLTRB(16, 6, 16, 0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(_typeLabel(a['activity_type'] as String? ?? ''),
                      style: const TextStyle(
                          fontSize: 11,
                          fontWeight: FontWeight.w600,
                          color: AppColors.textSecondary)),
                  const SizedBox(height: 2),
                  Text(
                    a['description'] as String? ?? '',
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                        fontSize: 13, color: AppColors.textPrimary),
                  ),
                  const SizedBox(height: 6),
                  const _Divider(),
                ],
              ),
            )),
      ],
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// DOCTOR CARDS
// ─────────────────────────────────────────────────────────────────────────────

class _DoctorAlertsCard extends StatelessWidget {
  final List<Map<String, dynamic>> alerts;
  const _DoctorAlertsCard({required this.alerts});

  Color _severityColor(String severity) {
    switch (severity) {
      case 'CRITICAL':
      case 'EMERGENCY':
        return AppColors.error;
      case 'WARNING':
        return AppColors.warning;
      default:
        return AppColors.info;
    }
  }

  @override
  Widget build(BuildContext context) {
    return _SectionCard(
      title: 'Active Alerts',
      icon: Icons.notifications_active_outlined,
      iconColor: AppColors.warning,
      children: [
        ...alerts.take(5).map((a) {
          final color = _severityColor(a['severity'] as String? ?? 'INFO');
          return Padding(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
            child: Column(
              children: [
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Container(
                      width: 4,
                      height: 40,
                      decoration: BoxDecoration(
                        color: color,
                        borderRadius: BorderRadius.circular(2),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(a['title'] as String? ?? '',
                              style: TextStyle(
                                  fontSize: 13,
                                  fontWeight: FontWeight.w600,
                                  color: color)),
                          Text(a['message'] as String? ?? '',
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(
                                  fontSize: 12,
                                  color: AppColors.textSecondary)),
                        ],
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                const _Divider(),
              ],
            ),
          );
        }),
      ],
    );
  }
}

class _DoctorMedicationCard extends StatelessWidget {
  final Map<String, dynamic> meds;
  final List<Map<String, dynamic>> adherence7day;
  const _DoctorMedicationCard(
      {required this.meds, required this.adherence7day});

  @override
  Widget build(BuildContext context) {
    final taken = meds['today_taken'] as int? ?? 0;
    final total = meds['today_total'] as int? ?? 0;
    final todayRate = meds['today_rate'] as int?;
    final weekRate = meds['week_rate'] as int? ?? 0;
    final active = meds['active_count'] as int? ?? 0;

    return _SectionCard(
      title: 'Medication Adherence',
      icon: Icons.medication_outlined,
      iconColor: AppColors.primary,
      children: [
        // Stats row
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: Row(
            children: [
              _MiniStat(
                  value: '$taken/$total',
                  label: 'Today',
                  color: _rateColor(todayRate ?? 0)),
              const SizedBox(width: 8),
              _MiniStat(
                  value: '$weekRate%',
                  label: '7-Day Rate',
                  color: _rateColor(weekRate)),
              const SizedBox(width: 8),
              _MiniStat(
                  value: '$active',
                  label: 'Active Meds',
                  color: AppColors.primary),
            ],
          ),
        ),
        const SizedBox(height: 14),

        // 7-day bar chart
        if (adherence7day.isNotEmpty) ...[
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Text('7-Day Adherence',
                style: GoogleFonts.lexend(
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    color: AppColors.textSecondary)),
          ),
          const SizedBox(height: 6),
          SizedBox(
            height: 110,
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: _AdherenceBarChart(data: adherence7day),
            ),
          ),
        ],
        const SizedBox(height: 4),
      ],
    );
  }

  Color _rateColor(int rate) {
    if (rate >= 80) return AppColors.success;
    if (rate >= 50) return AppColors.warning;
    return AppColors.error;
  }
}

class _AdherenceBarChart extends StatelessWidget {
  final List<Map<String, dynamic>> data;
  const _AdherenceBarChart({required this.data});

  @override
  Widget build(BuildContext context) {
    return BarChart(
      BarChartData(
        alignment: BarChartAlignment.spaceAround,
        maxY: 100,
        minY: 0,
        barTouchData: BarTouchData(
          enabled: true,
          touchTooltipData: BarTouchTooltipData(
            tooltipRoundedRadius: 8,
            getTooltipItem: (group, groupIndex, rod, rodIndex) {
              final d = data[groupIndex];
              return BarTooltipItem(
                '${d['rate']}%\n${_shortDate(d['date'] as String)}',
                const TextStyle(color: Colors.white, fontSize: 11),
              );
            },
          ),
        ),
        titlesData: FlTitlesData(
          show: true,
          bottomTitles: AxisTitles(
            sideTitles: SideTitles(
              showTitles: true,
              getTitlesWidget: (value, meta) {
                final idx = value.toInt();
                if (idx < 0 || idx >= data.length) {
                  return const SizedBox.shrink();
                }
                return Text(
                  _shortDate(data[idx]['date'] as String),
                  style: const TextStyle(
                      fontSize: 9, color: AppColors.textSecondary),
                );
              },
            ),
          ),
          leftTitles:
              const AxisTitles(sideTitles: SideTitles(showTitles: false)),
          topTitles:
              const AxisTitles(sideTitles: SideTitles(showTitles: false)),
          rightTitles:
              const AxisTitles(sideTitles: SideTitles(showTitles: false)),
        ),
        gridData: FlGridData(
          show: true,
          drawVerticalLine: false,
          horizontalInterval: 50,
          getDrawingHorizontalLine: (v) =>
              const FlLine(color: AppColors.border, strokeWidth: 1),
        ),
        borderData: FlBorderData(show: false),
        barGroups: List.generate(data.length, (i) {
          final rate = (data[i]['rate'] as num?)?.toDouble() ?? 0;
          return BarChartGroupData(
            x: i,
            barRods: [
              BarChartRodData(
                toY: rate,
                color: _barColor(rate.toInt()),
                width: 14,
                borderRadius: BorderRadius.circular(4),
              ),
            ],
          );
        }),
      ),
    );
  }

  String _shortDate(String iso) {
    try {
      final d = DateTime.parse(iso);
      const days = ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su'];
      return days[d.weekday - 1];
    } catch (_) {
      return iso.substring(5);
    }
  }

  Color _barColor(int rate) {
    if (rate >= 80) return AppColors.success;
    if (rate >= 50) return AppColors.warning;
    return AppColors.error;
  }
}

class _DoctorNutritionCard extends StatelessWidget {
  final Map<String, dynamic> nut;
  final List<Map<String, dynamic>> nutrition7day;
  const _DoctorNutritionCard({required this.nut, required this.nutrition7day});

  @override
  Widget build(BuildContext context) {
    final todayKcal = nut['today_kcal'] as int? ?? 0;
    final target = nut['daily_target'] as int?;
    final percent = nut['today_percent'] as int?;
    final consecutiveLow = nut['consecutive_low_days'] as int? ?? 0;
    final mealCount = (nut['meals_today'] as List?)?.length ?? 0;

    return _SectionCard(
      title: 'Nutrition',
      icon: Icons.restaurant_outlined,
      iconColor: Colors.orange,
      children: [
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: Row(
            children: [
              _MiniStat(
                value: '$todayKcal',
                label: 'kcal today',
                color: percent != null && percent < 50
                    ? AppColors.warning
                    : AppColors.success,
              ),
              const SizedBox(width: 8),
              _MiniStat(
                value: target != null ? '${percent ?? 0}%' : '—',
                label: 'of target',
                color: percent != null && percent < 50
                    ? AppColors.warning
                    : AppColors.primary,
              ),
              const SizedBox(width: 8),
              _MiniStat(
                value: '$consecutiveLow',
                label: 'low days',
                color: consecutiveLow >= 2 ? AppColors.error : AppColors.success,
              ),
            ],
          ),
        ),

        if (consecutiveLow >= 2) ...[
          const SizedBox(height: 10),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              decoration: BoxDecoration(
                color: AppColors.warning.withOpacity(0.08),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: AppColors.warning.withOpacity(0.4)),
              ),
              child: Row(
                children: [
                  const Icon(Icons.warning_amber_outlined,
                      size: 16, color: AppColors.warning),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      'Patient has had low caloric intake for $consecutiveLow consecutive days.',
                      style: const TextStyle(
                          fontSize: 12, color: AppColors.warning),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],

        const SizedBox(height: 14),

        // 7-day line chart
        if (nutrition7day.isNotEmpty) ...[
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Text('7-Day Caloric Intake',
                style: GoogleFonts.lexend(
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    color: AppColors.textSecondary)),
          ),
          const SizedBox(height: 6),
          SizedBox(
            height: 110,
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 8),
              child: _NutritionLineChart(
                  data: nutrition7day, target: target),
            ),
          ),
        ],
        const SizedBox(height: 4),
      ],
    );
  }
}

class _NutritionLineChart extends StatelessWidget {
  final List<Map<String, dynamic>> data;
  final int? target;
  const _NutritionLineChart({required this.data, this.target});

  @override
  Widget build(BuildContext context) {
    final maxKcal = data.fold<int>(
        (target ?? 2500),
        (m, d) => ((d['kcal'] as num?)?.toInt() ?? 0) > m
            ? (d['kcal'] as num).toInt()
            : m);

    final spots = List.generate(data.length, (i) {
      return FlSpot(i.toDouble(), ((data[i]['kcal'] as num?)?.toDouble() ?? 0));
    });

    return LineChart(
      LineChartData(
        minY: 0,
        maxY: maxKcal * 1.2,
        lineTouchData: LineTouchData(
          touchTooltipData: LineTouchTooltipData(
            getTooltipItems: (spots) => spots
                .map((s) => LineTooltipItem(
                    '${s.y.toInt()} kcal',
                    const TextStyle(color: Colors.white, fontSize: 11)))
                .toList(),
          ),
        ),
        titlesData: FlTitlesData(
          show: true,
          bottomTitles: AxisTitles(
            sideTitles: SideTitles(
              showTitles: true,
              getTitlesWidget: (value, meta) {
                final idx = value.toInt();
                if (idx < 0 || idx >= data.length) {
                  return const SizedBox.shrink();
                }
                return Text(
                  _shortDate(data[idx]['date'] as String),
                  style: const TextStyle(
                      fontSize: 9, color: AppColors.textSecondary),
                );
              },
            ),
          ),
          leftTitles:
              const AxisTitles(sideTitles: SideTitles(showTitles: false)),
          topTitles:
              const AxisTitles(sideTitles: SideTitles(showTitles: false)),
          rightTitles:
              const AxisTitles(sideTitles: SideTitles(showTitles: false)),
        ),
        gridData: FlGridData(
          show: true,
          drawVerticalLine: false,
          horizontalInterval: (maxKcal * 0.5).ceilToDouble(),
          getDrawingHorizontalLine: (v) =>
              const FlLine(color: AppColors.border, strokeWidth: 1),
        ),
        borderData: FlBorderData(show: false),
        extraLinesData: target != null
            ? ExtraLinesData(horizontalLines: [
                HorizontalLine(
                  y: target!.toDouble(),
                  color: AppColors.primary.withOpacity(0.4),
                  strokeWidth: 1.5,
                  dashArray: [5, 4],
                  label: HorizontalLineLabel(
                    show: true,
                    alignment: Alignment.topRight,
                    style: const TextStyle(
                        fontSize: 9, color: AppColors.primary),
                    labelResolver: (_) => 'target',
                  ),
                ),
              ])
            : null,
        lineBarsData: [
          LineChartBarData(
            spots: spots,
            isCurved: true,
            color: Colors.orange,
            barWidth: 2.5,
            dotData: const FlDotData(show: false),
            belowBarData: BarAreaData(
              show: true,
              color: Colors.orange.withOpacity(0.08),
            ),
          ),
        ],
      ),
    );
  }

  String _shortDate(String iso) {
    try {
      final d = DateTime.parse(iso);
      const days = ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su'];
      return days[d.weekday - 1];
    } catch (_) {
      return iso.substring(5);
    }
  }
}

class _DoctorVitalsCard extends StatelessWidget {
  final List<Map<String, dynamic>> vitals;
  const _DoctorVitalsCard({required this.vitals});

  @override
  Widget build(BuildContext context) {
    return _SectionCard(
      title: 'Latest Vitals',
      icon: Icons.monitor_heart_outlined,
      iconColor: AppColors.error,
      children: [
        ...vitals.take(6).map((v) {
          final isAnomaly = v['is_anomaly'] == true;
          return Column(
            children: [
              Padding(
                padding:
                    const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
                child: Row(
                  children: [
                    if (isAnomaly)
                      const Icon(Icons.warning_amber_rounded,
                          size: 14, color: AppColors.error)
                    else
                      const Icon(Icons.circle, size: 8, color: AppColors.border),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Text(v['type_name'] as String? ?? '',
                          style: TextStyle(
                              fontSize: 13,
                              color: isAnomaly
                                  ? AppColors.error
                                  : AppColors.textPrimary)),
                    ),
                    Text(
                      '${v['value']} ${v['unit'] ?? ''}'.trim(),
                      style: TextStyle(
                          fontSize: 13,
                          fontWeight: FontWeight.w600,
                          color: isAnomaly
                              ? AppColors.error
                              : AppColors.textPrimary),
                    ),
                  ],
                ),
              ),
              const _Divider(),
            ],
          );
        }),
      ],
    );
  }
}

class _MissedMedsCard extends StatelessWidget {
  final List<Map<String, dynamic>> missed;
  const _MissedMedsCard({required this.missed});

  @override
  Widget build(BuildContext context) {
    return _SectionCard(
      title: 'Missed / Skipped Today',
      icon: Icons.cancel_outlined,
      iconColor: AppColors.error,
      children: [
        ...missed.map((m) => Padding(
              padding: const EdgeInsets.fromLTRB(16, 6, 16, 0),
              child: Column(
                children: [
                  Row(
                    children: [
                      const Icon(Icons.radio_button_unchecked,
                          size: 14, color: AppColors.error),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Text(m['medication_name'] as String? ?? '',
                            style: const TextStyle(
                                fontSize: 13, color: AppColors.textPrimary)),
                      ),
                      if (m['scheduled_time'] != null)
                        Text(m['scheduled_time'] as String,
                            style: const TextStyle(
                                fontSize: 12,
                                color: AppColors.textSecondary)),
                    ],
                  ),
                  const SizedBox(height: 6),
                  const _Divider(),
                ],
              ),
            )),
      ],
    );
  }
}

class _MiniStat extends StatelessWidget {
  final String value;
  final String label;
  final Color color;

  const _MiniStat(
      {required this.value, required this.label, required this.color});

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 8),
        decoration: BoxDecoration(
          color: color.withOpacity(0.07),
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: color.withOpacity(0.2)),
        ),
        child: Column(
          children: [
            Text(value,
                style: GoogleFonts.lexend(
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                    color: color)),
            const SizedBox(height: 2),
            Text(label,
                textAlign: TextAlign.center,
                style: const TextStyle(
                    fontSize: 10, color: AppColors.textSecondary)),
          ],
        ),
      ),
    );
  }
}
