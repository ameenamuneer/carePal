from django.utils import timezone
from datetime import timedelta
from vitals.models import VitalReading
import logging

logger = logging.getLogger(__name__)


class AnomalyDetector:
    """
    Statistical anomaly detection using thresholds
    """
    
    def __init__(self, patient):
        self.patient = patient
    
    def detect_vital_clusters(self, vital_type_code, days=30):
        """
        Detect clusters of anomalies
        """
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        anomalies = VitalReading.objects.filter(
            patient=self.patient,
            vital_type__code=vital_type_code,
            measured_at__date__gte=start_date,
            measured_at__date__lte=end_date,
            is_anomaly=True
        ).order_by('measured_at')
        
        if not anomalies.exists():
            return {
                'clusters_detected': False,
                'clusters': []
            }
        
        # Group anomalies into clusters (within 24 hours)
        clusters = []
        current_cluster = []
        
        for anomaly in anomalies:
            if not current_cluster:
                current_cluster.append(anomaly)
            else:
                last_anomaly = current_cluster[-1]
                time_diff = (anomaly.measured_at - last_anomaly.measured_at).total_seconds() / 3600
                
                if time_diff <= 24:  # Within 24 hours
                    current_cluster.append(anomaly)
                else:
                    if len(current_cluster) >= 2:
                        clusters.append(current_cluster)
                    current_cluster = [anomaly]
        
        # Add last cluster
        if len(current_cluster) >= 2:
            clusters.append(current_cluster)
        
        cluster_summaries = []
        for cluster in clusters:
            cluster_summaries.append({
                'start_time': cluster[0].measured_at,
                'end_time': cluster[-1].measured_at,
                'count': len(cluster),
                'severity': self._cluster_severity(cluster),
                'avg_value': round(sum(r.value for r in cluster if r.value) / len(cluster), 2)
            })
        
        return {
            'clusters_detected': len(clusters) > 0,
            'cluster_count': len(clusters),
            'clusters': cluster_summaries
        }
    
    def detect_sudden_changes(self, vital_type_code, days=7):
        """
        Detect sudden significant changes in vitals
        """
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        readings = list(VitalReading.objects.filter(
            patient=self.patient,
            vital_type__code=vital_type_code,
            measured_at__date__gte=start_date,
            measured_at__date__lte=end_date,
            value__isnull=False
        ).order_by('measured_at').values_list('measured_at', 'value'))
        
        if len(readings) < 2:
            return {
                'sudden_changes_detected': False,
                'changes': []
            }
        
        changes = []
        for i in range(1, len(readings)):
            prev_time, prev_value = readings[i-1]
            curr_time, curr_value = readings[i]
            
            # Calculate percentage change
            if prev_value != 0:
                percent_change = abs((curr_value - prev_value) / prev_value * 100)
                
                # Significant change threshold: 20%
                if percent_change > 20:
                    changes.append({
                        'from_time': prev_time,
                        'to_time': curr_time,
                        'from_value': prev_value,
                        'to_value': curr_value,
                        'percent_change': round(percent_change, 2),
                        'direction': 'increase' if curr_value > prev_value else 'decrease'
                    })
        
        return {
            'sudden_changes_detected': len(changes) > 0,
            'change_count': len(changes),
            'changes': changes
        }
    
    def _cluster_severity(self, cluster):
        """Determine cluster severity"""
        critical_count = sum(1 for r in cluster if r.anomaly_severity == 'CRITICAL')
        high_count = sum(1 for r in cluster if r.anomaly_severity == 'HIGH')
        
        if critical_count > 0:
            return 'critical'
        elif high_count >= len(cluster) / 2:
            return 'high'
        else:
            return 'moderate'
