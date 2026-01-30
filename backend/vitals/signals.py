from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import VitalReading
from abdm.models import CareContext
from patients.models import PatientProfile
import logging
import uuid

logger = logging.getLogger(__name__)

@receiver(post_save, sender=VitalReading)
def push_vital_to_abdm(sender, instance, created, **kwargs):
    """
    When a vital reading is saved, ensure it's linked to an ABDM Care Context.
    This simulates "Pushing" data to the ABHA network by making it available
    under a linked context.
    """
    if not created:
        return

    try:
        patient = instance.patient
        logger.info(f"Signal Triggered: Patient={patient.id}, HasABHA={hasattr(patient, 'abha_profile')}")
        
        # Check if patient has ABHA linked
        if not hasattr(patient, 'abha_profile'):
            logger.info("Signal Skipped: No ABHA Profile")
            return

        abha_profile = patient.abha_profile
        
        # We use a single Care Context for all Vitals for simplicity,
        # or we could create one per month/session.
        # Let's use a unified "Vital Signs" context.
        
        context_id = f"vitals-{patient.id}"
        
        care_context, ctx_created = CareContext.objects.get_or_create(
            patient=patient,
            context_id=context_id,
            defaults={
                'abha_profile': abha_profile,
                'context_type': 'vitals',
                'display_name': 'Vital Signs Monitoring',
                'description': 'Continuous monitoring of vitals (BP, Heart Rate, Spo2)',
                'is_linked': True, # Auto-link since we are the HIP
                'from_date': instance.measured_at.date(),
                'to_date': instance.measured_at.date(),
            }
        )
        
        # Update date range if needed
        if not ctx_created:
            reading_date = instance.measured_at.date()
            if reading_date < care_context.from_date:
                care_context.from_date = reading_date
            if reading_date > care_context.to_date:
                care_context.to_date = reading_date
            care_context.save()
            
        logger.info(f"✅ [ABDM] Vital reading pushed to Care Context: {context_id}")
        
        # --- GENERATE FHIR WELLNESS RECORD ---
        # Refactored to use existing ABDMFHIRAdapter
        from fhir_integration.carepal_abdm_fhir_adapter import ABDMFHIRAdapter
        import json
        
        # 1. Prepare Data for Adapter
        vitals_data = {}
        vital_code = instance.vital_type.code.lower()
        
        if vital_code == 'bp' and instance.values:
            vitals_data['blood_pressure'] = {
                'systolic': float(instance.values.get('systolic', 0)),
                'diastolic': float(instance.values.get('diastolic', 0))
            }
        elif vital_code == 'hr' and instance.value:
            vitals_data['heart_rate'] = float(instance.value)
        elif vital_code == 'spo2' and instance.value:
            vitals_data['spo2'] = float(instance.value)
        elif vital_code == 'rr' and instance.value:
            vitals_data['respiratory_rate'] = float(instance.value)
        elif vital_code == 'temp' and instance.value:
            vitals_data['temperature'] = {
                'value': float(instance.value),
                'unit': 'C' # Defaulting to C, assuming unit conversion handled upstream or by adapter
            }
            if instance.unit and 'f' in instance.unit.lower():
                 vitals_data['temperature']['unit'] = 'F'

        if vitals_data:
            # 2. Patient Info
            patient_data = {
                'id': str(patient.id),
                'name': f"{patient.user.first_name} {patient.user.last_name}".strip(),
                'gender': patient.gender.lower() if patient.gender else 'unknown',
                'birth_date': str(patient.user.date_of_birth) if patient.user.date_of_birth else None,
                'phone': patient.user.phone_number
            }
            if hasattr(patient, 'abha_profile') and patient.abha_profile:
                 patient_data['abha_id'] = patient.abha_profile.abha_address

            # 3. Generate Bundle
            adapter = ABDMFHIRAdapter()
            fhir_bundle = adapter.create_wellness_record_bundle(
                patient_data=patient_data,
                vitals_data=vitals_data,
                recorded_at=instance.measured_at
            )
            
            # Log the FHIR JSON (Simulating the Push Payload)
            logger.info(f"📦 [FHIR GENERATED] Wellness Record Bundle ID: {fhir_bundle.get('id')}")
            logger.debug(json.dumps(fhir_bundle, indent=2))
        else:
            logger.warning(f"⚠️ [ABDM] No mapping found for vital type: {vital_code} - Skipping FHIR generation")

        
    except Exception as e:
        logger.error(f"❌ [ABDM] Failed to push vital data: {str(e)}")
