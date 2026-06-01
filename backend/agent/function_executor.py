"""
Function Executor
Executes functions called by Gemini AI Agent
Integrates with all CarePAL modules
"""

import logging
from typing import Dict, Any
from datetime import datetime, timedelta, date
from django.utils import timezone
from django.db import transaction

logger = logging.getLogger(__name__)


class FunctionExecutor:
    """
    Executes functions called by the AI agent
    Integrates with all backend modules
    """
    
    def __init__(self, patient_profile, user):
        """
        Initialize executor
        
        Args:
            patient_profile: PatientProfile instance
            user: User who initiated the session
        """
        self.patient = patient_profile
        self.user = user
    
    def execute(self, function_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a function call
        
        Args:
            function_name: Name of the function to execute
            parameters: Function parameters
        
        Returns:
            Dict with execution result
        """
        try:
            # Map function names to executor methods
            executor_map = {
                'create_alert': self._create_alert,
                'record_vital_reading': self._record_vital_reading,
                'get_medication_schedule': self._get_medication_schedule,
                'call_emergency_contact': self._call_emergency_contact,
                'call_family_member': self._call_family_member,
                'send_sms_notification': self._send_sms_notification,
                'log_patient_activity': self._log_patient_activity,
                'get_patient_vitals_summary': self._get_patient_vitals_summary,
                'check_medication_adherence': self._check_medication_adherence,
                'update_patient_notes': self._update_patient_notes,
                'schedule_task': self._schedule_task,
                'get_health_insights': self._get_health_insights,
                'escalate_alert': self._escalate_alert,
            }
            
            if function_name not in executor_map:
                return {
                    'success': False,
                    'error': f'Unknown function: {function_name}'
                }
            
            # Execute the function
            executor_method = executor_map[function_name]
            result = executor_method(parameters)
            
            logger.info(
                f"Executed {function_name} for patient {self.patient.id}: {result.get('success', False)}"
            )
            
            return result
        
        except Exception as e:
            logger.error(f"Error executing {function_name}: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @transaction.atomic
    def _create_alert(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create a health alert"""
        from alerts.models import Alert, AlertType
        
        try:
            # Get or create alert type
            alert_type_name = params.get('alert_type', 'GENERAL')
            alert_type, _ = AlertType.objects.get_or_create(
                code=alert_type_name,
                defaults={
                    'name': alert_type_name.replace('_', ' ').title(),
                    'description': f'AI-generated {alert_type_name} alert',
                    'default_severity': params['severity'],
                    'requires_acknowledgment': params['severity'] in ['CRITICAL', 'EMERGENCY'],
                    'auto_escalate_minutes': 30 if params['severity'] == 'CRITICAL' else None,
                }
            )
            
            # Create alert
            alert = Alert.objects.create(
                patient=self.patient,
                alert_type=alert_type,
                severity=params['severity'],
                title=params['title'],
                message=params['message'],
                source='AI_AGENT',
                context_data={
                    'created_by': 'ai_agent',
                    'session_user': self.user.id,
                }
            )
            
            # Trigger alert delivery (async task)
            from alerts.tasks import process_alert_delivery
            process_alert_delivery.delay(alert.id)
            
            return {
                'success': True,
                'alert_id': alert.id,
                'message': f'Alert created with ID {alert.id}'
            }
        
        except Exception as e:
            logger.error(f"Error creating alert: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @transaction.atomic
    def _record_vital_reading(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Record a vital sign reading"""
        from vitals.models import VitalReading, VitalType, DataSource
        
        try:
            # Get vital type
            vital_type = VitalType.objects.get(code=params['vital_type'])
            
            # Get or create "AI Agent" data source
            data_source, _ = DataSource.objects.get_or_create(
                patient=self.patient,
                source_type='MANUAL_ENTRY',
                device_type='MANUAL',
                device_name='AI Agent Voice Entry',
                defaults={'is_active': True}
            )
            
            # Prepare reading data
            reading_data = {
                'patient': self.patient,
                'vital_type': vital_type,
                'data_source': data_source,
                'measured_at': timezone.now(),
                'notes': params.get('notes', 'Recorded via AI voice assistant'),
            }
            
            # Handle blood pressure (multiple values)
            if params['vital_type'] == 'BP':
                reading_data['values'] = {
                    'systolic': params.get('systolic'),
                    'diastolic': params.get('diastolic')
                }
            else:
                reading_data['value'] = params.get('value')
            
            # Create reading
            reading = VitalReading.objects.create(**reading_data)
            
            # Trigger anomaly detection (async)
            from vitals.tasks import detect_vital_anomalies
            detect_vital_anomalies.delay(reading.id)
            
            return {
                'success': True,
                'reading_id': reading.id,
                'message': f'{vital_type.name} recorded successfully'
            }
        
        except VitalType.DoesNotExist:
            return {
                'success': False,
                'error': f'Unknown vital type: {params["vital_type"]}'
            }
        except Exception as e:
            logger.error(f"Error recording vital: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _get_medication_schedule(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get medication schedule"""
        from medications.models import Medication, MedicationSchedule, MedicationAdherence
        
        try:
            # Get date (default: today)
            target_date = params.get('date')
            if target_date:
                target_date = datetime.strptime(target_date, '%Y-%m-%d').date()
            else:
                target_date = timezone.now().date()
            
            # Get active medications
            medications = Medication.objects.filter(
                patient=self.patient,
                status='ACTIVE'
            ).prefetch_related('schedules', 'adherence_records')
            
            schedule_data = []
            for med in medications:
                for schedule in med.schedules.filter(is_active=True):
                    # Check if taken
                    adherence = MedicationAdherence.objects.filter(
                        medication=med,
                        schedule=schedule,
                        scheduled_date=target_date
                    ).first()
                    
                    schedule_data.append({
                        'medication_name': med.medication_name,
                        'dosage': med.dosage_amount,
                        'time': schedule.time_of_day.strftime('%H:%M') if schedule.time_of_day else None,
                        'time_label': schedule.time_label,
                        'with_food': schedule.with_food,
                        'status': adherence.status if adherence else 'SCHEDULED',
                        'is_critical': med.is_critical,
                    })
            
            return {
                'success': True,
                'date': target_date.isoformat(),
                'medications': schedule_data,
                'total_count': len(schedule_data)
            }
        
        except Exception as e:
            logger.error(f"Error getting medication schedule: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _call_emergency_contact(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Initiate emergency call"""
        from patients.models import EmergencyContact
        from .twilio_service import get_twilio_service
        
        try:
            # Get primary emergency contact
            emergency_contact = EmergencyContact.objects.filter(
                patient=self.patient,
                is_primary=True
            ).first()
            
            if not emergency_contact:
                # Get any emergency contact
                emergency_contact = EmergencyContact.objects.filter(
                    patient=self.patient
                ).first()
            
            if not emergency_contact:
                return {
                    'success': False,
                    'error': 'No emergency contact found'
                }
            
            # Initiate Twilio call
            twilio = get_twilio_service()
            call_result = twilio.initiate_emergency_call(
                to_number=emergency_contact.phone_number,
                patient_name=self.patient.user.get_full_name(),
                reason=params['reason'],
                urgency=params['urgency']
            )
            
            # Create alert
            self._create_alert({
                'severity': 'EMERGENCY',
                'title': 'Emergency Contact Called',
                'message': f"Called {emergency_contact.name}: {params['reason']}",
                'alert_type': 'EMERGENCY'
            })
            
            return {
                'success': True,
                'contact_name': emergency_contact.name,
                'call_sid': call_result.get('call_sid'),
                'message': f'Emergency call initiated to {emergency_contact.name}'
            }
        
        except Exception as e:
            logger.error(f"Error calling emergency contact: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _call_family_member(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Call a family member"""
        from family.models import FamilyMember
        from .twilio_service import get_twilio_service
        
        try:
            # Get primary family member
            family_member = FamilyMember.objects.filter(
                patient=self.patient,
                is_primary_contact=True,
                is_active=True
            ).first()
            
            if not family_member:
                return {
                    'success': False,
                    'error': 'No primary family member found'
                }
            
            # Initiate call
            twilio = get_twilio_service()
            call_result = twilio.initiate_family_call(
                to_number=family_member.phone_number,
                patient_name=self.patient.user.get_full_name(),
                reason=params['reason'],
                message=params['message']
            )
            
            return {
                'success': True,
                'family_member_name': family_member.user.get_full_name(),
                'call_sid': call_result.get('call_sid'),
                'message': f'Call initiated to {family_member.user.get_full_name()}'
            }
        
        except Exception as e:
            logger.error(f"Error calling family member: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _send_sms_notification(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Send SMS notification"""
        from .twilio_service import get_twilio_service
        from patients.models import EmergencyContact
        from family.models import FamilyMember
        
        try:
            recipient_type = params['recipient_type']
            message = params['message']
            
            # Get recipient phone number
            phone_number = None
            recipient_name = None
            
            if recipient_type == 'EMERGENCY_CONTACT':
                contact = EmergencyContact.objects.filter(
                    patient=self.patient,
                    is_primary=True
                ).first()
                if contact:
                    phone_number = contact.phone_number
                    recipient_name = contact.name
            
            elif recipient_type in ['FAMILY_MEMBER', 'PRIMARY_FAMILY']:
                family = FamilyMember.objects.filter(
                    patient=self.patient,
                    is_primary_contact=True,
                    is_active=True
                ).first()
                if family:
                    phone_number = family.phone_number
                    recipient_name = family.user.get_full_name()
            
            if not phone_number:
                return {
                    'success': False,
                    'error': f'No {recipient_type} found'
                }
            
            # Send SMS
            twilio = get_twilio_service()
            sms_result = twilio.send_sms(
                to_number=phone_number,
                message=f"CarePAL Alert - {self.patient.user.get_full_name()}: {message}"
            )
            
            return {
                'success': True,
                'recipient': recipient_name,
                'message_sid': sms_result.get('message_sid'),
                'message': f'SMS sent to {recipient_name}'
            }
        
        except Exception as e:
            logger.error(f"Error sending SMS: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _log_patient_activity(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Log patient activity to PatientActivityLog with current vitals snapshot"""
        from .models import PatientActivityLog
        from vitals.models import VitalReading

        try:
            # Resolve observed_at — use patient-mentioned time or now
            observed_at_raw = params.get('observed_at')
            if observed_at_raw:
                try:
                    from dateutil import parser as dateutil_parser
                    observed_at = dateutil_parser.parse(observed_at_raw)
                    if timezone.is_naive(observed_at):
                        observed_at = timezone.make_aware(observed_at)
                except Exception:
                    observed_at = timezone.now()
            else:
                observed_at = timezone.now()

            # Snapshot the latest vitals for context
            vitals_snapshot = {}
            try:
                recent_readings = (
                    VitalReading.objects
                    .filter(patient=self.patient, is_deleted=False)
                    .select_related('vital_type')
                    .order_by('vital_type_id', '-measured_at')
                    .distinct('vital_type_id')
                )
                for r in recent_readings:
                    vitals_snapshot[r.vital_type.code] = {
                        'display': r.get_display_value(),
                        'measured_at': r.measured_at.isoformat(),
                        'unit': r.vital_type.unit,
                    }
            except Exception as ve:
                logger.warning(f"Could not snapshot vitals: {ve}")

            log_entry = PatientActivityLog.objects.create(
                patient=self.patient,
                activity_type=params['activity_type'],
                description=params['description'],
                details=params.get('details') or {},
                observed_at=observed_at,
                vitals_snapshot=vitals_snapshot,
                ai_confidence=params.get('ai_confidence', 'MEDIUM'),
                is_notable=params.get('is_notable', False),
                notable_reason=params.get('notable_reason', ''),
                tags=params.get('tags') or [],
            )

            return {
                'success': True,
                'log_id': log_entry.id,
                'message': 'Activity logged successfully'
            }

        except Exception as e:
            logger.error(f"Error logging activity: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _get_patient_vitals_summary(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get vitals summary"""
        from vitals.models import VitalReading, VitalType
        from django.db.models import Avg, Min, Max, Count
        
        try:
            days = params.get('days', 7)
            vital_type_code = params.get('vital_type', 'all')
            
            since_date = timezone.now() - timedelta(days=days)
            
            summary = {}
            
            if vital_type_code == 'all':
                vital_types = VitalType.objects.filter(is_active=True)
            else:
                vital_types = VitalType.objects.filter(code=vital_type_code)
            
            for vtype in vital_types:
                readings = VitalReading.objects.filter(
                    patient=self.patient,
                    vital_type=vtype,
                    measured_at__gte=since_date,
                    is_deleted=False
                )
                
                if vtype.code == 'BP':
                    # Blood pressure special handling
                    summary[vtype.code] = {
                        'count': readings.count(),
                        'latest': readings.order_by('-measured_at').first().values if readings.exists() else None
                    }
                else:
                    stats = readings.aggregate(
                        avg=Avg('value'),
                        min=Min('value'),
                        max=Max('value'),
                        count=Count('id')
                    )
                    summary[vtype.code] = stats
            
            return {
                'success': True,
                'period_days': days,
                'vitals': summary
            }
        
        except Exception as e:
            logger.error(f"Error getting vitals summary: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _check_medication_adherence(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Check medication adherence"""
        from medications.models import MedicationAdherence
        
        try:
            days = params.get('days', 7)
            since_date = timezone.now().date() - timedelta(days=days)
            
            adherence_records = MedicationAdherence.objects.filter(
                medication__patient=self.patient,
                scheduled_date__gte=since_date
            )
            
            total = adherence_records.count()
            taken = adherence_records.filter(status='TAKEN').count()
            missed = adherence_records.filter(status='MISSED').count()
            
            adherence_rate = (taken / total * 100) if total > 0 else 0
            
            return {
                'success': True,
                'period_days': days,
                'total_scheduled': total,
                'taken': taken,
                'missed': missed,
                'adherence_rate': round(adherence_rate, 1),
                'status': 'EXCELLENT' if adherence_rate >= 90 else 'GOOD' if adherence_rate >= 75 else 'NEEDS_IMPROVEMENT'
            }
        
        except Exception as e:
            logger.error(f"Error checking adherence: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _update_patient_notes(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Add notes to patient record"""
        # Could add to PatientProfile or create a Notes model
        try:
            note_text = f"[{params['note_type']}] {params['note_text']}"
            
            # For now, log as event
            from .models import AgentEventLog
            event = AgentEventLog.objects.create(
                patient=self.patient,
                event_type='MESSAGE_RECEIVED',
                event_data={
                    'note_type': params['note_type'],
                    'note': params['note_text'],
                    'added_by': 'ai_agent'
                },
                severity='INFO'
            )
            
            return {
                'success': True,
                'message': 'Note added successfully'
            }
        
        except Exception as e:
            logger.error(f"Error updating notes: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _schedule_task(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Schedule a future task"""
        from family.models import CareSchedule
        
        try:
            # Parse date and time
            scheduled_date = datetime.strptime(params['scheduled_date'], '%Y-%m-%d').date()
            scheduled_time = None
            if params.get('scheduled_time'):
                scheduled_time = datetime.strptime(params['scheduled_time'], '%H:%M').time()
            
            # Create care schedule task
            task = CareSchedule.objects.create(
                patient=self.patient,
                task_type=params['task_type'],
                title=params['title'],
                description=params.get('description', ''),
                scheduled_date=scheduled_date,
                scheduled_time=scheduled_time,
                created_by=self.user,
                status='PENDING'
            )
            
            return {
                'success': True,
                'task_id': task.id,
                'message': f'Task scheduled for {scheduled_date}'
            }
        
        except Exception as e:
            logger.error(f"Error scheduling task: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _get_health_insights(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get AI health insights"""
        from analytics.engines.metrics_engine import MetricsEngine
        from analytics.insights.ai_enhanced_insights import AIEnhancedInsights
        from analytics.insights.rule_based_insights import RuleBasedInsights
        
        try:
            days = params.get('days', 30)
            end_date = timezone.now().date()
            start_date = end_date - timedelta(days=days)
            
            # Compute metrics
            metrics_engine = MetricsEngine(self.patient, start_date, end_date)
            metrics = metrics_engine.compute_all_metrics()
            
            # Generate insights
            rule_insights = RuleBasedInsights(self.patient).generate_all_insights(metrics)
            
            return {
                'success': True,
                'period_days': days,
                'health_score': metrics['overall']['health_score'],
                'insights': rule_insights[:5],  # Top 5 insights
            }
        
        except Exception as e:
            logger.error(f"Error getting insights: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _escalate_alert(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Escalate an alert"""
        from alerts.models import Alert
        
        try:
            alert = Alert.objects.get(id=params['alert_id'])
            
            # Escalate
            alert.is_escalated = True
            alert.escalated_at = timezone.now()
            alert.escalation_level += 1
            alert.metadata['escalation_reason'] = params['reason']
            alert.metadata['escalated_by'] = 'ai_agent'
            alert.save()
            
            # Trigger escalation delivery
            from alerts.tasks import process_alert_delivery
            process_alert_delivery.delay(alert.id)
            
            return {
                'success': True,
                'alert_id': alert.id,
                'escalation_level': alert.escalation_level,
                'message': 'Alert escalated successfully'
            }
        
        except Alert.DoesNotExist:
            return {
                'success': False,
                'error': f'Alert {params["alert_id"]} not found'
            }
        except Exception as e:
            logger.error(f"Error escalating alert: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
