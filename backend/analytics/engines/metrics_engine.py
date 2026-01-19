from django.db.models import Avg, Count, Min, Max, StdDev, Q
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from vitals.models import VitalReading, VitalType
from medications.models import Medication, MedicationAdherence
from alerts.models import Alert
from devices.models import DeviceSyncLog
import logging

logger = logging.getLogger(__name__)


class MetricsEngine:
    """
    Pure statistical calculations - 100% deterministic
    """
    
    def __init__(self, patient):
        self.patient = patient
    
    def compute_period_metrics(self, start_date, end_date):
        """
        Compute all metrics for a given period
        Returns structured data dictionary
        """
        metrics = {
            'vitals': self._compute_vital_metrics(start_date, end_date),
            'medications': self._compute_medication_metrics(start_date, end_date),
            'alerts': self._compute_alert_metrics(start_date, end_date),
            'devices': self._compute_device_metrics(start_date, end_date),
            'overall': {},
        }
        
        # Compute overall health score
        metrics['overall']['health_score'] = self._compute_health_score(metrics)
        metrics['overall']['trend_direction'] = self._compute_trend_direction(metrics)
        metrics['overall']['data_completeness'] = self._compute_data_completeness(
            start_date, end_date
        )
        
        return metrics
    
    def _compute_vital_metrics(self, start_date, end_date):
        """Compute vital sign statistics"""
        vitals_summary = {}
        
        # Get all vital types for this patient
        vital_types = VitalType.objects.filter(is_active=True)
        
        for vital_type in vital_types:
            readings = VitalReading.objects.filter(
                patient=self.patient,
                vital_type=vital_type,
                measured_at__date__gte=start_date,
                measured_at__date__lte=end_date
            )
            
            if not readings.exists():
                continue
            
            # Extract values based on vital type
            if vital_type.code == 'BP':
                # Blood pressure has systolic and diastolic
                systolic_values = []
                diastolic_values = []
                
                for reading in readings:
                    if 'systolic' in reading.values:
                        systolic_values.append(reading.values['systolic'])
                    if 'diastolic' in reading.values:
                        diastolic_values.append(reading.values['diastolic'])
                
                vitals_summary[vital_type.code] = {
                    'readings_count': readings.count(),
                    'avg_systolic': round(sum(systolic_values) / len(systolic_values), 1) if systolic_values else None,
                    'min_systolic': min(systolic_values) if systolic_values else None,
                    'max_systolic': max(systolic_values) if systolic_values else None,
                    'avg_diastolic': round(sum(diastolic_values) / len(diastolic_values), 1) if diastolic_values else None,
                    'min_diastolic': min(diastolic_values) if diastolic_values else None,
                    'max_diastolic': max(diastolic_values) if diastolic_values else None,
                    'anomaly_count': readings.filter(is_anomaly=True).count(),
                    'trend': self._calculate_simple_trend(systolic_values) if systolic_values else 'stable',
                }
            else:
                # Single value vitals (HR, SpO2, Temp, etc)
                values = [float(reading.value) for reading in readings if reading.value is not None]
                
                if values:
                    vitals_summary[vital_type.code] = {
                        'readings_count': len(values),
                        'average': round(sum(values) / len(values), 1),
                        'minimum': min(values),
                        'maximum': max(values),
                        'std_dev': round(self._calculate_std_dev(values), 2),
                        'anomaly_count': readings.filter(is_anomaly=True).count(),
                        'trend': self._calculate_simple_trend(values),
                    }
        
        return vitals_summary
    
    def _compute_medication_metrics(self, start_date, end_date):
        """Compute medication adherence statistics"""
        adherence_records = MedicationAdherence.objects.filter(
            medication__patient=self.patient,
            scheduled_date__gte=start_date,
            scheduled_date__lte=end_date
        )
        
        total_scheduled = adherence_records.count()
        
        if total_scheduled == 0:
            return {
                'adherence_rate': 0,
                'total_scheduled': 0,
                'total_taken': 0,
                'total_missed': 0,
                'total_skipped': 0,
                'critical_misses': 0,
            }
        
        taken = adherence_records.filter(status='TAKEN').count()
        missed = adherence_records.filter(status='MISSED').count()
        skipped = adherence_records.filter(status='SKIPPED').count()
        
        # Critical medication misses
        critical_meds = Medication.objects.filter(
            patient=self.patient,
            is_critical=True
        ).values_list('id', flat=True)
        
        critical_misses = adherence_records.filter(
            medication_id__in=critical_meds,
            status='MISSED'
        ).count()
        
        adherence_rate = (taken / total_scheduled * 100) if total_scheduled > 0 else 0
        
        return {
            'adherence_rate': round(adherence_rate, 2),
            'total_scheduled': total_scheduled,
            'total_taken': taken,
            'total_missed': missed,
            'total_skipped': skipped,
            'critical_misses': critical_misses,
            'trend': self._calculate_adherence_trend(start_date, end_date),
        }
    
    def _compute_alert_metrics(self, start_date, end_date):
        """Compute alert statistics"""
        alerts = Alert.objects.filter(
            patient=self.patient,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        )
        
        total = alerts.count()
        
        # Count by severity
        severity_counts = {
            'info': alerts.filter(severity='INFO').count(),
            'warning': alerts.filter(severity='WARNING').count(),
            'critical': alerts.filter(severity='CRITICAL').count(),
            'emergency': alerts.filter(severity='EMERGENCY').count(),
        }
        
        # Response time for acknowledged alerts
        acknowledged = alerts.filter(acknowledged_at__isnull=False)
        
        if acknowledged.exists():
            total_response_time = 0
            count = 0
            
            for alert in acknowledged:
                response_time = (alert.acknowledged_at - alert.created_at).total_seconds() / 60
                total_response_time += response_time
                count += 1
            
            avg_response_time = total_response_time / count if count > 0 else 0
        else:
            avg_response_time = None
        
        escalated_count = alerts.filter(is_escalated=True).count()
        
        return {
            'total': total,
            'by_severity': severity_counts,
            'avg_response_time_minutes': round(avg_response_time, 2) if avg_response_time else None,
            'escalated_count': escalated_count,
            'escalation_rate': round((escalated_count / total * 100), 2) if total > 0 else 0,
        }
    
    def _compute_device_metrics(self, start_date, end_date):
        """Compute device sync statistics"""
        sync_logs = DeviceSyncLog.objects.filter(
            data_source__patient=self.patient,
            started_at__date__gte=start_date,
            started_at__date__lte=end_date
        )
        
        total_syncs = sync_logs.count()
        
        if total_syncs == 0:
            return {
                'total_syncs': 0,
                'success_rate': 0,
                'failed_syncs': 0,
            }
        
        successful = sync_logs.filter(status='SUCCESS').count()
        failed = sync_logs.filter(status='FAILED').count()
        
        success_rate = (successful / total_syncs * 100) if total_syncs > 0 else 0
        
        return {
            'total_syncs': total_syncs,
            'successful_syncs': successful,
            'failed_syncs': failed,
            'success_rate': round(success_rate, 2),
        }
    
    def _compute_health_score(self, metrics):
        """
        Calculate overall health score (0-100)
        Weighted combination of various metrics
        """
        score = 100
        
        # Medication adherence (weight: 30%)
        med_adherence = metrics['medications'].get('adherence_rate', 0)
        score -= (100 - med_adherence) * 0.3
        
        # Alert severity (weight: 30%)
        alerts = metrics['alerts']
        if alerts['total'] > 0:
            # Penalize based on severity
            emergency_penalty = alerts['by_severity']['emergency'] * 15
            critical_penalty = alerts['by_severity']['critical'] * 10
            warning_penalty = alerts['by_severity']['warning'] * 5
            
            score -= min(30, emergency_penalty + critical_penalty + warning_penalty)
        
        # Vital anomalies (weight: 20%)
        total_anomalies = 0
        total_readings = 0
        
        for vital_code, vital_data in metrics['vitals'].items():
            total_anomalies += vital_data.get('anomaly_count', 0)
            total_readings += vital_data.get('readings_count', 0)
        
        if total_readings > 0:
            anomaly_rate = (total_anomalies / total_readings) * 100
            score -= min(20, anomaly_rate * 2)
        
        # Device sync reliability (weight: 20%)
        device_success_rate = metrics['devices'].get('success_rate', 100)
        score -= (100 - device_success_rate) * 0.2
        
        return max(0, min(100, int(score)))
    
    def _compute_trend_direction(self, metrics):
        """Determine overall trend direction"""
        # Simple heuristic based on medication adherence and alert trends
        
        med_trend = metrics['medications'].get('trend', 'stable')
        
        # Count critical/emergency alerts
        critical_alerts = (
            metrics['alerts']['by_severity']['critical'] +
            metrics['alerts']['by_severity']['emergency']
        )
        
        if critical_alerts > 5:
            return 'declining'
        elif med_trend == 'improving' and critical_alerts == 0:
            return 'improving'
        elif med_trend == 'declining' or critical_alerts > 2:
            return 'declining'
        else:
            return 'stable'
    
    def _compute_data_completeness(self, start_date, end_date):
        """Calculate data completeness percentage"""
        days_in_period = (end_date - start_date).days + 1
        
        # Expected: At least 1 vital reading per day
        vital_days = VitalReading.objects.filter(
            patient=self.patient,
            measured_at__date__gte=start_date,
            measured_at__date__lte=end_date
        ).values('measured_at__date').distinct().count()
        
        vital_completeness = (vital_days / days_in_period * 100) if days_in_period > 0 else 0
        
        # Expected: All scheduled medications logged
        scheduled_meds = MedicationAdherence.objects.filter(
            medication__patient=self.patient,
            scheduled_date__gte=start_date,
            scheduled_date__lte=end_date
        ).count()
        
        logged_meds = MedicationAdherence.objects.filter(
            medication__patient=self.patient,
            scheduled_date__gte=start_date,
            scheduled_date__lte=end_date
        ).exclude(status='SCHEDULED').count()
        
        med_completeness = (logged_meds / scheduled_meds * 100) if scheduled_meds > 0 else 100
        
        # Average
        overall_completeness = (vital_completeness + med_completeness) / 2
        
        return round(overall_completeness, 2)
    
    def _calculate_simple_trend(self, values):
        """Calculate simple trend: improving, stable, declining"""
        if len(values) < 2:
            return 'stable'
        
        # Split into first half and second half
        mid = len(values) // 2
        first_half_avg = sum(values[:mid]) / len(values[:mid])
        second_half_avg = sum(values[mid:]) / len(values[mid:])
        
        # Calculate percentage change
        if first_half_avg == 0:
            return 'stable'
        
        change_percent = ((second_half_avg - first_half_avg) / first_half_avg) * 100
        
        if change_percent > 5:
            return 'increasing'
        elif change_percent < -5:
            return 'decreasing'
        else:
            return 'stable'
    
    def _calculate_std_dev(self, values):
        """Calculate standard deviation"""
        if len(values) < 2:
            return 0
        
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return variance ** 0.5
    
    def _calculate_adherence_trend(self, start_date, end_date):
        """Calculate medication adherence trend"""
        # Split period into two halves
        mid_date = start_date + (end_date - start_date) / 2
        
        first_half = MedicationAdherence.objects.filter(
            medication__patient=self.patient,
            scheduled_date__gte=start_date,
            scheduled_date__lt=mid_date
        )
        
        second_half = MedicationAdherence.objects.filter(
            medication__patient=self.patient,
            scheduled_date__gte=mid_date,
            scheduled_date__lte=end_date
        )
        
        first_total = first_half.count()
        first_taken = first_half.filter(status='TAKEN').count()
        
        second_total = second_half.count()
        second_taken = second_half.filter(status='TAKEN').count()
        
        if first_total == 0 or second_total == 0:
            return 'stable'
        
        first_rate = (first_taken / first_total) * 100
        second_rate = (second_taken / second_total) * 100
        
        change = second_rate - first_rate
        
        if change > 5:
            return 'improving'
        elif change < -5:
            return 'declining'
        else:
            return 'stable'
