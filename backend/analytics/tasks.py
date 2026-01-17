from celery import shared_task
from django.utils import timezone
from datetime import timedelta, datetime
from django.db.models import Count, Avg
from .models import (
    HealthMetric, TrendAnalysis, RiskScore, InsightRecord,
    HealthReport, ScheduledReport, DashboardSnapshot
)
from patients.models import PatientProfile
from .engines.metrics_engine import MetricsEngine
from .engines.trend_analyzer import TrendAnalyzer
from .insights.rule_based_insights import RuleBasedInsights
from .insights.ai_enhanced_insights import AIEnhancedInsights
import logging

logger = logging.getLogger(__name__)


@shared_task
def compute_daily_metrics():
    """
    Compute daily health metrics for all active patients
    Run at midnight daily
    """
    patients = PatientProfile.objects.filter(is_active=True)
    
    yesterday = timezone.now().date() - timedelta(days=1)
    
    computed_count = 0
    error_count = 0
    
    for patient in patients:
        try:
            compute_health_metrics.delay(
                patient_id=patient.id,
                period_type='daily',
                start_date=str(yesterday),
                end_date=str(yesterday)
            )
            computed_count += 1
        except Exception as e:
            logger.error(f"Error queuing daily metrics for patient {patient.id}: {str(e)}")
            error_count += 1
    
    logger.info(f"Queued daily metrics for {computed_count} patients, {error_count} errors")
    return {'computed': computed_count, 'errors': error_count}


@shared_task
def compute_weekly_metrics():
    """
    Compute weekly health metrics for all active patients
    Run on Sundays at midnight
    """
    patients = PatientProfile.objects.filter(is_active=True)
    
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=7)
    
    computed_count = 0
    
    for patient in patients:
        try:
            compute_health_metrics.delay(
                patient_id=patient.id,
                period_type='weekly',
                start_date=str(start_date),
                end_date=str(end_date)
            )
            computed_count += 1
        except Exception as e:
            logger.error(f"Error queuing weekly metrics for patient {patient.id}: {str(e)}")
    
    logger.info(f"Queued weekly metrics for {computed_count} patients")
    return computed_count


@shared_task
def compute_monthly_metrics():
    """
    Compute monthly health metrics for all active patients
    Run on 1st of each month at midnight
    """
    patients = PatientProfile.objects.filter(is_active=True)
    
    today = timezone.now().date()
    start_date = today.replace(day=1) - timedelta(days=1)  # Last day of previous month
    start_date = start_date.replace(day=1)  # First day of previous month
    end_date = today.replace(day=1) - timedelta(days=1)  # Last day of previous month
    
    computed_count = 0
    
    for patient in patients:
        try:
            compute_health_metrics.delay(
                patient_id=patient.id,
                period_type='monthly',
                start_date=str(start_date),
                end_date=str(end_date)
            )
            computed_count += 1
        except Exception as e:
            logger.error(f"Error queuing monthly metrics for patient {patient.id}: {str(e)}")
    
    logger.info(f"Queued monthly metrics for {computed_count} patients")
    return computed_count


@shared_task
def compute_health_metrics(patient_id, period_type, start_date, end_date):
    """
    Compute health metrics for a specific patient and period
    """
    start_time = timezone.now()
    
    try:
        patient = PatientProfile.objects.get(id=patient_id)
        
        # Convert string dates to date objects
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        # Initialize metrics engine
        engine = MetricsEngine(patient)
        
        # Compute metrics
        metrics = engine.compute_period_metrics(start_date, end_date)
        
        # Generate insights
        insights_gen = RuleBasedInsights(patient)
        insights = insights_gen.generate_insights(metrics)
        
        # Save insights
        for insight in insights:
            InsightRecord.objects.create(
                patient=patient,
                insight_type='rule_based',
                insight_text=insight['text'],
                insight_category=insight['category'],
                source='metrics_engine',
                source_version='1.0.0',
                validation_passed=True,
                confidence_score=insight['confidence'],
                source_metrics=insight.get('data_points', {})
            )
        
        # Create or update health metric record
        computation_duration = (timezone.now() - start_time).total_seconds()
        
        health_metric, created = HealthMetric.objects.update_or_create(
            patient=patient,
            period_type=period_type,
            period_start=start_date,
            defaults={
                'period_end': end_date,
                'vitals_summary': metrics.get('vitals', {}),
                'medication_adherence_rate': metrics.get('medications', {}).get('adherence_rate', 0),
                'total_doses_scheduled': metrics.get('medications', {}).get('total_scheduled', 0),
                'total_doses_taken': metrics.get('medications', {}).get('total_taken', 0),
                'total_doses_missed': metrics.get('medications', {}).get('total_missed', 0),
                'total_doses_skipped': metrics.get('medications', {}).get('total_skipped', 0),
                'critical_medication_misses': metrics.get('medications', {}).get('critical_misses', 0),
                'total_alerts': metrics.get('alerts', {}).get('total', 0),
                'info_alerts': metrics.get('alerts', {}).get('by_severity', {}).get('info', 0),
                'warning_alerts': metrics.get('alerts', {}).get('by_severity', {}).get('warning', 0),
                'critical_alerts': metrics.get('alerts', {}).get('by_severity', {}).get('critical', 0),
                'emergency_alerts': metrics.get('alerts', {}).get('by_severity', {}).get('emergency', 0),
                'avg_alert_response_time_minutes': metrics.get('alerts', {}).get('avg_response_time_minutes'),
                'escalated_alerts_count': metrics.get('alerts', {}).get('escalated_count', 0),
                'device_sync_success_rate': metrics.get('devices', {}).get('success_rate', 0),
                'total_device_syncs': metrics.get('devices', {}).get('total_syncs', 0),
                'failed_device_syncs': metrics.get('devices', {}).get('failed_syncs', 0),
                'overall_health_score': metrics.get('overall', {}).get('health_score', 0),
                'health_score_category': _get_health_category(metrics.get('overall', {}).get('health_score', 0)),
                'trend_direction': metrics.get('overall', {}).get('trend_direction', 'stable'),
                'data_completeness_percentage': metrics.get('overall', {}).get('data_completeness', 0),
                'computation_duration_seconds': computation_duration,
            }
        )
        
        logger.info(
            f"Computed {period_type} metrics for patient {patient_id}: "
            f"health_score={health_metric.overall_health_score}, "
            f"duration={computation_duration:.2f}s"
        )
        
        return health_metric.id
    
    except PatientProfile.DoesNotExist:
        logger.error(f"Patient {patient_id} not found")
        return None
    except Exception as e:
        logger.error(f"Error computing metrics for patient {patient_id}: {str(e)}")
        raise


def _get_health_category(score):
    """Helper to determine health category from score"""
    if score >= 85:
        return 'excellent'
    elif score >= 70:
        return 'good'
    elif score >= 50:
        return 'fair'
    else:
        return 'poor'


@shared_task
def compute_trend_analysis():
    """
    Compute trend analysis for all active patients
    Run weekly
    """
    patients = PatientProfile.objects.filter(is_active=True)
    
    analysis_count = 0
    
    for patient in patients:
        try:
            analyzer = TrendAnalyzer(patient)
            
            # Analyze BP vs medication adherence correlation
            bp_med_correlation = analyzer.analyze_medication_vital_impact(
                medication_id=None,  # Will analyze all BP medications
                vital_type_code='BP',
                days=30
            )
            
            if bp_med_correlation.get('impact') != 'insufficient_data':
                TrendAnalysis.objects.create(
                    patient=patient,
                    analysis_type='correlation',
                    metric_1='medication_adherence',
                    metric_2='bp_stability',
                    analysis_start_date=timezone.now().date() - timedelta(days=30),
                    analysis_end_date=timezone.now().date(),
                    data_points_count=bp_med_correlation.get('sample_sizes', {}).get('taken_days', 0),
                    findings=[
                        f"Impact: {bp_med_correlation.get('impact')}",
                        f"Average BP when medication taken: {bp_med_correlation.get('avg_when_taken')}",
                        f"Average BP when medication missed: {bp_med_correlation.get('avg_when_missed')}",
                    ],
                    statistical_summary=bp_med_correlation,
                    clinical_significance=bp_med_correlation.get('impact', 'unknown')
                )
                
                analysis_count += 1
        
        except Exception as e:
            logger.error(f"Error computing trend analysis for patient {patient.id}: {str(e)}")
    
    logger.info(f"Computed trend analysis for {analysis_count} patients")
    return analysis_count


@shared_task
def compute_risk_scores():
    """
    Compute risk scores for all active patients
    Run every 6 hours
    """
    patients = PatientProfile.objects.filter(is_active=True)
    
    risk_count = 0
    
    for patient in patients:
        try:
            # Get recent metrics
            recent_metric = HealthMetric.objects.filter(
                patient=patient,
                period_type='daily'
            ).order_by('-period_end').first()
            
            if not recent_metric:
                continue
            
            # Simple rule-based risk scoring
            risk_score = 0.0
            risk_factors = []
            
            # Health score factor
            if recent_metric.overall_health_score < 50:
                risk_score += 0.3
                risk_factors.append("Low overall health score")
            elif recent_metric.overall_health_score < 70:
                risk_score += 0.15
                risk_factors.append("Moderate health score")
            
            # Medication adherence factor
            if recent_metric.medication_adherence_rate < 60:
                risk_score += 0.25
                risk_factors.append("Poor medication adherence")
            elif recent_metric.medication_adherence_rate < 80:
                risk_score += 0.1
                risk_factors.append("Suboptimal medication adherence")
            
            # Critical medications missed
            if recent_metric.critical_medication_misses > 0:
                risk_score += 0.2
                risk_factors.append(f"{recent_metric.critical_medication_misses} critical medication doses missed")
            
            # Alert frequency
            if recent_metric.emergency_alerts > 0:
                risk_score += 0.15
                risk_factors.append(f"{recent_metric.emergency_alerts} emergency alerts")
            if recent_metric.critical_alerts >= 3:
                risk_score += 0.1
                risk_factors.append(f"{recent_metric.critical_alerts} critical alerts")
            
            # Trend direction
            if recent_metric.trend_direction == 'declining':
                risk_score += 0.1
                risk_factors.append("Declining health trend")
            
            # Cap at 1.0
            risk_score = min(1.0, risk_score)
            
            # Only create if risk is meaningful
            if risk_score >= 0.2:
                # Invalidate old risk scores
                RiskScore.objects.filter(
                    patient=patient,
                    risk_type='deterioration',
                    is_active=True
                ).update(is_active=False)
                
                # Create new risk score
                RiskScore.objects.create(
                    patient=patient,
                    risk_type='deterioration',
                    risk_score=risk_score,
                    risk_factors=risk_factors,
                    model_type='rule_based',
                    model_version='1.0.0',
                    model_confidence=1.0,
                    recommended_actions=_get_recommendations(risk_score, risk_factors),
                    requires_human_review=risk_score >= 0.7
                )
                
                risk_count += 1
        
        except Exception as e:
            logger.error(f"Error computing risk score for patient {patient.id}: {str(e)}")
    
    logger.info(f"Computed risk scores for {risk_count} patients")
    return risk_count


def _get_recommendations(risk_score, risk_factors):
    """Generate recommendations based on risk score"""
    recommendations = []
    
    if risk_score >= 0.7:
        recommendations.append("Schedule urgent medical review")
        recommendations.append("Increase monitoring frequency")
        recommendations.append("Notify family members and emergency contacts")
    elif risk_score >= 0.4:
        recommendations.append("Schedule doctor appointment within 1 week")
        recommendations.append("Review medication adherence barriers")
        recommendations.append("Increase family check-ins")
    else:
        recommendations.append("Continue regular monitoring")
        recommendations.append("Address specific concerns identified")
    
    return recommendations


@shared_task
def generate_health_report(report_id, include_ai_insights=True, generate_pdf=True, 
                          generate_excel=False, template_id=None):
    """
    Generate a health report
    """
    try:
        report = HealthReport.objects.get(id=report_id)
        patient = report.patient
        
        # Get metrics for period
        metrics_list = HealthMetric.objects.filter(
            patient=patient,
            period_start__gte=report.report_start_date,
            period_end__lte=report.report_end_date
        ).order_by('period_start')
        
        # Get insights
        insights = InsightRecord.objects.filter(
            patient=patient,
            created_at__date__gte=report.report_start_date,
            created_at__date__lte=report.report_end_date,
            validation_passed=True
        ).order_by('-confidence_score')[:10]
        
        # Get risk scores
        risk_scores = RiskScore.objects.filter(
            patient=patient,
            computed_at__date__gte=report.report_start_date,
            computed_at__date__lte=report.report_end_date
        ).order_by('-computed_at')
        
        # Build report data
        report_data = {
            'patient': {
                'name': patient.user.get_full_name(),
                'age': patient.age,
                'gender': patient.gender,
            },
            'period': {
                'start': str(report.report_start_date),
                'end': str(report.report_end_date),
            },
            'metrics': [
                {
                    'period': f"{m.period_start} to {m.period_end}",
                    'health_score': m.overall_health_score,
                    'medication_adherence': float(m.medication_adherence_rate),
                    'vitals': m.vitals_summary,
                    'alerts': {
                        'total': m.total_alerts,
                        'critical': m.critical_alerts,
                        'emergency': m.emergency_alerts
                    }
                }
                for m in metrics_list
            ],
            'insights': [
                {
                    'text': i.insight_text,
                    'category': i.insight_category,
                    'confidence': float(i.confidence_score)
                }
                for i in insights
            ],
            'risk_assessment': [
                {
                    'type': r.get_risk_type_display(),
                    'score': float(r.risk_score),
                    'category': r.risk_category,
                    'factors': r.risk_factors,
                    'recommendations': r.recommended_actions
                }
                for r in risk_scores
            ]
        }
        
        # Save report data
        report.report_data = report_data
        report.status = 'completed'
        report.save()
        
        # TODO: Generate PDF and Excel files
        # This would use libraries like ReportLab or WeasyPrint for PDF
        # and openpyxl for Excel
        
        logger.info(f"Generated report {report_id} for patient {patient.id}")
        return report_id
    
    except HealthReport.DoesNotExist:
        logger.error(f"Report {report_id} not found")
        return None
    except Exception as e:
        logger.error(f"Error generating report {report_id}: {str(e)}")
        
        # Update report status
        try:
            report = HealthReport.objects.get(id=report_id)
            report.status = 'failed'
            report.generation_error = str(e)
            report.save()
        except:
            pass
        
        raise


@shared_task
def process_scheduled_reports():
    """
    Process scheduled reports that are due
    Run hourly
    """
    now = timezone.now()
    
    due_reports = ScheduledReport.objects.filter(
        is_active=True,
        next_generation_at__lte=now
    )
    
    generated_count = 0
    
    for scheduled in due_reports:
        try:
            # Determine date range based on frequency
            end_date = now.date()
            
            if scheduled.frequency == 'daily':
                start_date = end_date - timedelta(days=1)
            elif scheduled.frequency == 'weekly':
                start_date = end_date - timedelta(days=7)
            elif scheduled.frequency == 'monthly':
                start_date = end_date - timedelta(days=30)
            else:
                continue
            
            # Create report
            report = HealthReport.objects.create(
                patient=scheduled.patient,
                generated_by=scheduled.created_by,
                report_type=scheduled.report_type,
                report_title=f"{scheduled.report_name} - {end_date}",
                report_start_date=start_date,
                report_end_date=end_date,
                status='generating',
                ai_enhanced=scheduled.include_ai_insights
            )
            
            # Generate report
            generate_health_report.delay(
                report_id=report.id,
                include_ai_insights=scheduled.include_ai_insights,
                generate_pdf=scheduled.generate_pdf,
                generate_excel=scheduled.generate_excel
            )
            
            # Update scheduled report
            scheduled.last_generated_at = now
            scheduled.generation_count += 1
            
            # Calculate next generation time
            if scheduled.frequency == 'daily':
                scheduled.next_generation_at = now + timedelta(days=1)
            elif scheduled.frequency == 'weekly':
                scheduled.next_generation_at = now + timedelta(weeks=1)
            elif scheduled.frequency == 'monthly':
                scheduled.next_generation_at = now + timedelta(days=30)
            
            scheduled.save()
            
            generated_count += 1
        
        except Exception as e:
            logger.error(f"Error processing scheduled report {scheduled.id}: {str(e)}")
    
    logger.info(f"Processed {generated_count} scheduled reports")
    return generated_count


@shared_task
def cleanup_old_dashboard_snapshots():
    """
    Delete expired dashboard snapshots
    Run every hour
    """
    cutoff_time = timezone.now()
    
    deleted = DashboardSnapshot.objects.filter(
        expires_at__lte=cutoff_time
    ).delete()
    
    logger.info(f"Deleted {deleted[0]} expired dashboard snapshots")
    return deleted[0]


@shared_task
def invalidate_dashboard_cache(patient_id):
    """
    Invalidate dashboard cache for a patient
    Called when new data is added
    """
    DashboardSnapshot.objects.filter(
        patient_id=patient_id,
        is_valid=True
    ).update(is_valid=False)
    
    logger.info(f"Invalidated dashboard cache for patient {patient_id}")
    return True
