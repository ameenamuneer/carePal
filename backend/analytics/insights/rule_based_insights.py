from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class RuleBasedInsights:
    """
    Deterministic rule-based insights
    100% reproducible for same inputs
    """
    
    def __init__(self, patient):
        self.patient = patient
    
    def generate_insights(self, metrics):
        """
        Generate all insights from metrics
        Returns list of insight objects
        """
        insights = []
        
        # Vital insights
        insights.extend(self._generate_vital_insights(metrics.get('vitals', {})))
        
        # Medication insights
        insights.extend(self._generate_medication_insights(metrics.get('medications', {})))
        
        # Alert insights
        insights.extend(self._generate_alert_insights(metrics.get('alerts', {})))
        
        # Overall health insights
        insights.extend(self._generate_overall_insights(metrics.get('overall', {})))
        
        # Cross-metric insights
        insights.extend(self._generate_correlation_insights(metrics))
        
        return insights
    
    def _generate_vital_insights(self, vitals_data):
        """Generate insights from vital signs data"""
        insights = []
        
        for vital_code, vital_metrics in vitals_data.items():
            # Blood Pressure specific insights
            if vital_code == 'BP':
                avg_systolic = vital_metrics.get('avg_systolic')
                avg_diastolic = vital_metrics.get('avg_diastolic')
                
                if avg_systolic and avg_diastolic:
                    if avg_systolic >= 140 or avg_diastolic >= 90:
                        insights.append({
                            'category': 'vitals',
                            'subcategory': 'blood_pressure',
                            'severity': 'high',
                            'text': f"Average blood pressure ({avg_systolic}/{avg_diastolic} mmHg) is above normal range (120/80 mmHg)",
                            'recommendation': "Schedule a doctor visit to discuss blood pressure management and review medications",
                            'confidence': 1.0,
                            'source': 'rule_based',
                            'data_points': {
                                'avg_systolic': avg_systolic,
                                'avg_diastolic': avg_diastolic,
                                'readings_count': vital_metrics.get('readings_count')
                            }
                        })
                    elif avg_systolic >= 130 or avg_diastolic >= 85:
                        insights.append({
                            'category': 'vitals',
                            'subcategory': 'blood_pressure',
                            'severity': 'moderate',
                            'text': f"Average blood pressure ({avg_systolic}/{avg_diastolic} mmHg) is in pre-hypertension range",
                            'recommendation': "Monitor blood pressure closely and review lifestyle factors (diet, exercise, stress)",
                            'confidence': 1.0,
                            'source': 'rule_based',
                            'data_points': {
                                'avg_systolic': avg_systolic,
                                'avg_diastolic': avg_diastolic
                            }
                        })
                    else:
                        insights.append({
                            'category': 'vitals',
                            'subcategory': 'blood_pressure',
                            'severity': 'normal',
                            'text': f"Blood pressure is well-controlled at {avg_systolic}/{avg_diastolic} mmHg",
                            'recommendation': "Continue current management plan",
                            'confidence': 1.0,
                            'source': 'rule_based',
                            'data_points': {
                                'avg_systolic': avg_systolic,
                                'avg_diastolic': avg_diastolic
                            }
                        })
                
                # Trend insight
                trend = vital_metrics.get('trend', 'stable')
                if trend == 'increasing':
                    insights.append({
                        'category': 'vitals',
                        'subcategory': 'blood_pressure',
                        'severity': 'moderate',
                        'text': "Blood pressure shows an upward trend over the period",
                        'recommendation': "Review recent lifestyle changes, medication adherence, and stress levels",
                        'confidence': 1.0,
                        'source': 'rule_based',
                        'data_points': {'trend': trend}
                    })
                elif trend == 'decreasing':
                    insights.append({
                        'category': 'vitals',
                        'subcategory': 'blood_pressure',
                        'severity': 'positive',
                        'text': "Blood pressure shows a downward trend - positive improvement",
                        'recommendation': "Continue current treatment plan",
                        'confidence': 1.0,
                        'source': 'rule_based',
                        'data_points': {'trend': trend}
                    })
            
            # Heart Rate insights
            elif vital_code == 'HR':
                avg_hr = vital_metrics.get('average')
                
                if avg_hr:
                    if avg_hr > 100:
                        insights.append({
                            'category': 'vitals',
                            'subcategory': 'heart_rate',
                            'severity': 'high',
                            'text': f"Average heart rate ({avg_hr} bpm) is elevated (normal: 60-100 bpm)",
                            'recommendation': "Consult doctor about elevated heart rate - may indicate stress, dehydration, or medication side effects",
                            'confidence': 1.0,
                            'source': 'rule_based',
                            'data_points': {'avg_hr': avg_hr}
                        })
                    elif avg_hr < 60:
                        insights.append({
                            'category': 'vitals',
                            'subcategory': 'heart_rate',
                            'severity': 'moderate',
                            'text': f"Average heart rate ({avg_hr} bpm) is below normal range",
                            'recommendation': "Monitor for symptoms like dizziness or fatigue. Consult doctor if symptomatic",
                            'confidence': 1.0,
                            'source': 'rule_based',
                            'data_points': {'avg_hr': avg_hr}
                        })
                    else:
                        insights.append({
                            'category': 'vitals',
                            'subcategory': 'heart_rate',
                            'severity': 'normal',
                            'text': f"Heart rate is within normal range at {avg_hr} bpm",
                            'recommendation': "Continue regular monitoring",
                            'confidence': 1.0,
                            'source': 'rule_based',
                            'data_points': {'avg_hr': avg_hr}
                        })
            
            # SpO2 insights
            elif vital_code == 'SPO2':
                avg_spo2 = vital_metrics.get('average')
                
                if avg_spo2:
                    if avg_spo2 < 95:
                        insights.append({
                            'category': 'vitals',
                            'subcategory': 'oxygen_saturation',
                            'severity': 'high',
                            'text': f"Average oxygen saturation ({avg_spo2}%) is below normal (95-100%)",
                            'recommendation': "Consult doctor immediately - low oxygen levels require medical attention",
                            'confidence': 1.0,
                            'source': 'rule_based',
                            'data_points': {'avg_spo2': avg_spo2}
                        })
                    else:
                        insights.append({
                            'category': 'vitals',
                            'subcategory': 'oxygen_saturation',
                            'severity': 'normal',
                            'text': f"Oxygen saturation is excellent at {avg_spo2}%",
                            'recommendation': "Continue current management",
                            'confidence': 1.0,
                            'source': 'rule_based',
                            'data_points': {'avg_spo2': avg_spo2}
                        })
            
            # Anomaly insights for all vitals
            anomaly_count = vital_metrics.get('anomaly_count', 0)
            readings_count = vital_metrics.get('readings_count', 0)
            
            if readings_count > 0:
                anomaly_rate = (anomaly_count / readings_count) * 100
                
                if anomaly_rate > 20:
                    insights.append({
                        'category': 'vitals',
                        'subcategory': vital_code.lower(),
                        'severity': 'high',
                        'text': f"High rate of anomalous {vital_code} readings ({anomaly_rate:.1f}% - {anomaly_count} out of {readings_count})",
                        'recommendation': "Increased monitoring frequency recommended. Review with healthcare provider",
                        'confidence': 1.0,
                        'source': 'rule_based',
                        'data_points': {
                            'anomaly_count': anomaly_count,
                            'readings_count': readings_count,
                            'anomaly_rate': round(anomaly_rate, 2)
                        }
                    })
                elif anomaly_rate > 10:
                    insights.append({
                        'category': 'vitals',
                        'subcategory': vital_code.lower(),
                        'severity': 'moderate',
                        'text': f"Moderate rate of anomalous {vital_code} readings ({anomaly_rate:.1f}%)",
                        'recommendation': "Continue monitoring - discuss with doctor at next visit",
                        'confidence': 1.0,
                        'source': 'rule_based',
                        'data_points': {
                            'anomaly_count': anomaly_count,
                            'readings_count': readings_count
                        }
                    })
        
        return insights
    
    def _generate_medication_insights(self, med_data):
        """Generate insights from medication data"""
        insights = []
        
        adherence_rate = med_data.get('adherence_rate', 0)
        critical_misses = med_data.get('critical_misses', 0)
        total_missed = med_data.get('total_missed', 0)
        
        # Adherence rate insights
        if adherence_rate >= 95:
            insights.append({
                'category': 'medications',
                'subcategory': 'adherence',
                'severity': 'positive',
                'text': f"Excellent medication adherence at {adherence_rate:.1f}%",
                'recommendation': "Keep up the great work! Continue following your medication schedule",
                'confidence': 1.0,
                'source': 'rule_based',
                'data_points': {'adherence_rate': adherence_rate}
            })
        elif adherence_rate >= 80:
            insights.append({
                'category': 'medications',
                'subcategory': 'adherence',
                'severity': 'normal',
                'text': f"Good medication adherence at {adherence_rate:.1f}%",
                'recommendation': "Consider setting reminders to reach 95%+ adherence for optimal results",
                'confidence': 1.0,
                'source': 'rule_based',
                'data_points': {'adherence_rate': adherence_rate}
            })
        elif adherence_rate >= 60:
            insights.append({
                'category': 'medications',
                'subcategory': 'adherence',
                'severity': 'moderate',
                'text': f"Medication adherence needs improvement at {adherence_rate:.1f}%",
                'recommendation': "Set multiple reminders and consider using a pill organizer. Discuss barriers with doctor",
                'confidence': 1.0,
                'source': 'rule_based',
                'data_points': {'adherence_rate': adherence_rate}
            })
        else:
            insights.append({
                'category': 'medications',
                'subcategory': 'adherence',
                'severity': 'high',
                'text': f"Low medication adherence at {adherence_rate:.1f}% - urgent attention needed",
                'recommendation': "Contact healthcare provider immediately to discuss adherence challenges and alternative strategies",
                'confidence': 1.0,
                'source': 'rule_based',
                'data_points': {'adherence_rate': adherence_rate}
            })
        
        # Critical medication insights
        if critical_misses > 0:
            insights.append({
                'category': 'medications',
                'subcategory': 'critical_medications',
                'severity': 'high',
                'text': f"{critical_misses} critical medication dose(s) missed during this period",
                'recommendation': "Critical medications must be taken as prescribed. Set up automatic reminders and backup alerts",
                'confidence': 1.0,
                'source': 'rule_based',
                'data_points': {'critical_misses': critical_misses}
            })
        
        # Trend insights
        trend = med_data.get('trend', 'stable')
        if trend == 'declining':
            insights.append({
                'category': 'medications',
                'subcategory': 'adherence',
                'severity': 'moderate',
                'text': "Medication adherence is declining over the period",
                'recommendation': "Identify barriers to adherence - discuss with family or healthcare provider for support",
                'confidence': 1.0,
                'source': 'rule_based',
                'data_points': {'trend': trend}
            })
        elif trend == 'improving':
            insights.append({
                'category': 'medications',
                'subcategory': 'adherence',
                'severity': 'positive',
                'text': "Medication adherence is improving - great progress!",
                'recommendation': "Continue with current strategies that are working well",
                'confidence': 1.0,
                'source': 'rule_based',
                'data_points': {'trend': trend}
            })
        
        return insights
    
    def _generate_alert_insights(self, alert_data):
        """Generate insights from alert data"""
        insights = []
        
        total_alerts = alert_data.get('total', 0)
        by_severity = alert_data.get('by_severity', {})
        escalation_rate = alert_data.get('escalation_rate', 0)
        avg_response_time = alert_data.get('avg_response_time_minutes')
        
        # Alert frequency insights
        if by_severity.get('emergency', 0) > 0:
            insights.append({
                'category': 'alerts',
                'subcategory': 'emergency',
                'severity': 'high',
                'text': f"{by_severity['emergency']} emergency alert(s) triggered during this period",
                'recommendation': "Emergency alerts require immediate medical review. Ensure emergency contacts are updated",
                'confidence': 1.0,
                'source': 'rule_based',
                'data_points': {'emergency_count': by_severity['emergency']}
            })
        
        if by_severity.get('critical', 0) >= 5:
            insights.append({
                'category': 'alerts',
                'subcategory': 'critical',
                'severity': 'high',
                'text': f"High number of critical alerts ({by_severity['critical']}) this period",
                'recommendation': "Review health management plan with doctor - may need medication or lifestyle adjustments",
                'confidence': 1.0,
                'source': 'rule_based',
                'data_points': {'critical_count': by_severity['critical']}
            })
        
        if total_alerts == 0:
            insights.append({
                'category': 'alerts',
                'subcategory': 'overall',
                'severity': 'positive',
                'text': "No alerts triggered during this period - excellent health stability",
                'recommendation': "Continue current health management practices",
                'confidence': 1.0,
                'source': 'rule_based',
                'data_points': {'total_alerts': 0}
            })
        
        # Escalation insights
        if escalation_rate > 30:
            insights.append({
                'category': 'alerts',
                'subcategory': 'response',
                'severity': 'moderate',
                'text': f"High alert escalation rate ({escalation_rate:.1f}%) indicates delayed responses",
                'recommendation': "Review alert notification settings and ensure family members can respond quickly",
                'confidence': 1.0,
                'source': 'rule_based',
                'data_points': {'escalation_rate': escalation_rate}
            })
        
        # Response time insights
        if avg_response_time and avg_response_time > 60:
            insights.append({
                'category': 'alerts',
                'subcategory': 'response',
                'severity': 'moderate',
                'text': f"Average alert response time is {avg_response_time:.0f} minutes",
                'recommendation': "Consider enabling additional notification channels for faster response",
                'confidence': 1.0,
                'source': 'rule_based',
                'data_points': {'avg_response_time_minutes': avg_response_time}
            })
        elif avg_response_time and avg_response_time <= 30:
            insights.append({
                'category': 'alerts',
                'subcategory': 'response',
                'severity': 'positive',
                'text': f"Excellent alert response time at {avg_response_time:.0f} minutes",
                'recommendation': "Maintain current notification and response procedures",
                'confidence': 1.0,
                'source': 'rule_based',
                'data_points': {'avg_response_time_minutes': avg_response_time}
            })
        
        return insights
    
    def _generate_overall_insights(self, overall_data):
        """Generate overall health insights"""
        insights = []
        
        health_score = overall_data.get('health_score', 0)
        trend_direction = overall_data.get('trend_direction', 'stable')
        data_completeness = overall_data.get('data_completeness', 0)
        
        # Health score insights
        if health_score >= 85:
            insights.append({
                'category': 'overall',
                'subcategory': 'health_score',
                'severity': 'positive',
                'text': f"Overall health score is excellent at {health_score}/100",
                'recommendation': "Continue maintaining healthy lifestyle and medication adherence",
                'confidence': 1.0,
                'source': 'rule_based',
                'data_points': {'health_score': health_score}
            })
        elif health_score >= 70:
            insights.append({
                'category': 'overall',
                'subcategory': 'health_score',
                'severity': 'normal',
                'text': f"Overall health score is good at {health_score}/100",
                'recommendation': "Room for improvement - focus on areas flagged in other insights",
                'confidence': 1.0,
                'source': 'rule_based',
                'data_points': {'health_score': health_score}
            })
        elif health_score >= 50:
            insights.append({
                'category': 'overall',
                'subcategory': 'health_score',
                'severity': 'moderate',
                'text': f"Overall health score needs attention at {health_score}/100",
                'recommendation': "Schedule doctor visit to review health management plan",
                'confidence': 1.0,
                'source': 'rule_based',
                'data_points': {'health_score': health_score}
            })
        else:
            insights.append({
                'category': 'overall',
                'subcategory': 'health_score',
                'severity': 'high',
                'text': f"Overall health score is concerning at {health_score}/100",
                'recommendation': "Urgent medical review recommended - multiple health parameters need attention",
                'confidence': 1.0,
                'source': 'rule_based',
                'data_points': {'health_score': health_score}
            })
        
        # Trend insights
        if trend_direction == 'improving':
            insights.append({
                'category': 'overall',
                'subcategory': 'trend',
                'severity': 'positive',
                'text': "Overall health trend is improving",
                'recommendation': "Positive progress! Continue current treatment and lifestyle approaches",
                'confidence': 1.0,
                'source': 'rule_based',
                'data_points': {'trend': trend_direction}
            })
        elif trend_direction == 'declining':
            insights.append({
                'category': 'overall',
                'subcategory': 'trend',
                'severity': 'moderate',
                'text': "Overall health trend is declining",
                'recommendation': "Review recent changes and discuss with healthcare provider",
                'confidence': 1.0,
                'source': 'rule_based',
                'data_points': {'trend': trend_direction}
            })
        
        # Data completeness insights
        if data_completeness < 70:
            insights.append({
                'category': 'overall',
                'subcategory': 'data_quality',
                'severity': 'moderate',
                'text': f"Health data completeness is {data_completeness:.1f}% - more consistent monitoring needed",
                'recommendation': "Regular vital measurements and medication logging improve health insights accuracy",
                'confidence': 1.0,
                'source': 'rule_based',
                'data_points': {'data_completeness': data_completeness}
            })
        
        return insights
    
    def _generate_correlation_insights(self, metrics):
        """Generate insights from cross-metric correlations"""
        insights = []
        
        # Check medication adherence vs vitals stability
        med_adherence = metrics.get('medications', {}).get('adherence_rate', 100)
        vitals_anomalies = sum(
            v.get('anomaly_count', 0)
            for v in metrics.get('vitals', {}).values()
        )
        vitals_readings = sum(
            v.get('readings_count', 0)
            for v in metrics.get('vitals', {}).values()
        )
        
        if vitals_readings > 0:
            anomaly_rate = (vitals_anomalies / vitals_readings) * 100
            
            if med_adherence < 80 and anomaly_rate > 15:
                insights.append({
                    'category': 'correlation',
                    'subcategory': 'medication_vitals',
                    'severity': 'high',
                    'text': f"Low medication adherence ({med_adherence:.1f}%) correlates with high vital anomaly rate ({anomaly_rate:.1f}%)",
                    'recommendation': "Improving medication adherence may help stabilize vital signs",
                    'confidence': 0.85,
                    'source': 'rule_based',
                    'data_points': {
                        'med_adherence': med_adherence,
                        'anomaly_rate': round(anomaly_rate, 2)
                    }
                })
        
        return insights
