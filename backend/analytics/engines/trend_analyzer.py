from django.db.models import Avg, Count
from django.utils import timezone
from datetime import timedelta
from vitals.models import VitalReading
from medications.models import MedicationAdherence
import logging

logger = logging.getLogger(__name__)


class TrendAnalyzer:
    """
    Statistical trend analysis - correlations and patterns
    """
    
    def __init__(self, patient):
        self.patient = patient
    
    def analyze_vital_correlation(self, vital_type_1, vital_type_2, days=30):
        """
        Analyze correlation between two vital signs
        Returns correlation coefficient and interpretation
        """
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        # Get readings for both vitals
        readings_1 = list(VitalReading.objects.filter(
            patient=self.patient,
            vital_type__code=vital_type_1,
            measured_at__date__gte=start_date,
            measured_at__date__lte=end_date,
            value__isnull=False
        ).order_by('measured_at').values_list('measured_at', 'value'))
        
        readings_2 = list(VitalReading.objects.filter(
            patient=self.patient,
            vital_type__code=vital_type_2,
            measured_at__date__gte=start_date,
            measured_at__date__lte=end_date,
            value__isnull=False
        ).order_by('measured_at').values_list('measured_at', 'value'))
        
        if len(readings_1) < 3 or len(readings_2) < 3:
            return {
                'correlation_coefficient': None,
                'interpretation': 'insufficient_data',
                'data_points': min(len(readings_1), len(readings_2))
            }
        
        # Align readings by timestamp (within 1 hour)
        aligned_pairs = []
        for ts1, val1 in readings_1:
            for ts2, val2 in readings_2:
                time_diff = abs((ts1 - ts2).total_seconds())
                if time_diff < 3600:  # Within 1 hour
                    aligned_pairs.append((val1, val2))
                    break
        
        if len(aligned_pairs) < 3:
            return {
                'correlation_coefficient': None,
                'interpretation': 'insufficient_aligned_data',
                'data_points': len(aligned_pairs)
            }
        
        # Calculate Pearson correlation
        correlation = self._pearson_correlation(aligned_pairs)
        
        return {
            'correlation_coefficient': round(correlation, 4),
            'interpretation': self._interpret_correlation(correlation),
            'strength': self._correlation_strength(correlation),
            'data_points': len(aligned_pairs)
        }
    
    def analyze_medication_vital_impact(self, medication_id, vital_type_code, days=30):
        """
        Analyze impact of medication adherence on vital signs
        """
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        # Get adherence records
        adherence = MedicationAdherence.objects.filter(
            medication_id=medication_id,
            scheduled_date__gte=start_date,
            scheduled_date__lte=end_date
        ).order_by('scheduled_date')
        
        if adherence.count() < 7:
            return {
                'impact': 'insufficient_data',
                'confidence': 0
            }
        
        # Get vital readings
        vitals = VitalReading.objects.filter(
            patient=self.patient,
            vital_type__code=vital_type_code,
            measured_at__date__gte=start_date,
            measured_at__date__lte=end_date
        ).order_by('measured_at')
        
        # Days with medication taken vs missed
        taken_days = set(adherence.filter(status='TAKEN').values_list('scheduled_date', flat=True))
        missed_days = set(adherence.filter(status='MISSED').values_list('scheduled_date', flat=True))
        
        # Average vitals on taken vs missed days
        taken_vitals = []
        missed_vitals = []
        
        for vital in vitals:
            vital_date = vital.measured_at.date()
            if vital_date in taken_days:
                taken_vitals.append(vital.value)
            elif vital_date in missed_days:
                missed_vitals.append(vital.value)
        
        if not taken_vitals or not missed_vitals:
            return {
                'impact': 'insufficient_data',
                'confidence': 0
            }
        
        avg_taken = sum(taken_vitals) / len(taken_vitals)
        avg_missed = sum(missed_vitals) / len(missed_vitals)
        
        difference = avg_taken - avg_missed
        percent_change = (difference / avg_missed * 100) if avg_missed != 0 else 0
        
        return {
            'avg_when_taken': round(avg_taken, 2),
            'avg_when_missed': round(avg_missed, 2),
            'difference': round(difference, 2),
            'percent_change': round(percent_change, 2),
            'impact': self._interpret_medication_impact(percent_change),
            'confidence': min(len(taken_vitals), len(missed_vitals)) / 10,  # 0-1 scale
            'sample_sizes': {
                'taken_days': len(taken_vitals),
                'missed_days': len(missed_vitals)
            }
        }
    
    def detect_time_patterns(self, vital_type_code, days=30):
        """
        Detect time-of-day or day-of-week patterns in vitals
        """
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        readings = VitalReading.objects.filter(
            patient=self.patient,
            vital_type__code=vital_type_code,
            measured_at__date__gte=start_date,
            measured_at__date__lte=end_date,
            value__isnull=False
        )
        
        # Time of day patterns
        morning = []  # 6-12
        afternoon = []  # 12-18
        evening = []  # 18-24
        night = []  # 0-6
        
        for reading in readings:
            hour = reading.measured_at.hour
            if 6 <= hour < 12:
                morning.append(reading.value)
            elif 12 <= hour < 18:
                afternoon.append(reading.value)
            elif 18 <= hour < 24:
                evening.append(reading.value)
            else:
                night.append(reading.value)
        
        time_patterns = {}
        if morning:
            time_patterns['morning'] = round(sum(morning) / len(morning), 2)
        if afternoon:
            time_patterns['afternoon'] = round(sum(afternoon) / len(afternoon), 2)
        if evening:
            time_patterns['evening'] = round(sum(evening) / len(evening), 2)
        if night:
            time_patterns['night'] = round(sum(night) / len(night), 2)
        
        # Day of week patterns
        day_patterns = {}
        for reading in readings:
            day_name = reading.measured_at.strftime('%A')
            if day_name not in day_patterns:
                day_patterns[day_name] = []
            day_patterns[day_name].append(reading.value)
        
        day_averages = {
            day: round(sum(values) / len(values), 2)
            for day, values in day_patterns.items()
        }
        
        return {
            'time_of_day': time_patterns,
            'day_of_week': day_averages,
            'pattern_detected': self._has_significant_pattern(time_patterns, day_averages)
        }
    
    def _pearson_correlation(self, pairs):
        """Calculate Pearson correlation coefficient"""
        n = len(pairs)
        if n < 2:
            return 0
        
        x_values = [x for x, y in pairs]
        y_values = [y for x, y in pairs]
        
        mean_x = sum(x_values) / n
        mean_y = sum(y_values) / n
        
        numerator = sum((x - mean_x) * (y - mean_y) for x, y in pairs)
        
        sum_sq_x = sum((x - mean_x) ** 2 for x in x_values)
        sum_sq_y = sum((y - mean_y) ** 2 for y in y_values)
        
        denominator = (sum_sq_x * sum_sq_y) ** 0.5
        
        if denominator == 0:
            return 0
        
        return numerator / denominator
    
    def _interpret_correlation(self, correlation):
        """Interpret correlation coefficient"""
        abs_corr = abs(correlation)
        
        if abs_corr > 0.7:
            strength = 'strong'
        elif abs_corr > 0.5:
            strength = 'moderate'
        elif abs_corr > 0.3:
            strength = 'weak'
        else:
            strength = 'negligible'
        
        direction = 'positive' if correlation > 0 else 'negative'
        
        return f"{strength}_{direction}"
    
    def _correlation_strength(self, correlation):
        """Return correlation strength category"""
        abs_corr = abs(correlation)
        
        if abs_corr > 0.7:
            return 'strong'
        elif abs_corr > 0.5:
            return 'moderate'
        elif abs_corr > 0.3:
            return 'weak'
        else:
            return 'negligible'
    
    def _interpret_medication_impact(self, percent_change):
        """Interpret medication impact on vitals"""
        if abs(percent_change) < 5:
            return 'minimal_impact'
        elif percent_change < -10:
            return 'significant_positive_impact'
        elif percent_change > 10:
            return 'significant_negative_impact'
        elif percent_change < 0:
            return 'moderate_positive_impact'
        else:
            return 'moderate_negative_impact'
    
    def _has_significant_pattern(self, time_patterns, day_patterns):
        """Check if there's a significant time/day pattern"""
        if not time_patterns or not day_patterns:
            return False
        
        # Check time of day variation
        time_values = list(time_patterns.values())
        if len(time_values) > 1:
            time_range = max(time_values) - min(time_values)
            time_avg = sum(time_values) / len(time_values)
            time_variation = (time_range / time_avg * 100) if time_avg != 0 else 0
            
            if time_variation > 10:  # >10% variation
                return True
        
        # Check day of week variation
        day_values = list(day_patterns.values())
        if len(day_values) > 1:
            day_range = max(day_values) - min(day_values)
            day_avg = sum(day_values) / len(day_values)
            day_variation = (day_range / day_avg * 100) if day_avg != 0 else 0
            
            if day_variation > 10:  # >10% variation
                return True
        
        return False
