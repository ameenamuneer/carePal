from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from vitals.models import VitalReading
from .carepal_abdm_fhir_adapter import ABDMFHIRAdapter

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_vitals_as_fhir(request, vitals_id):
    """
    Get a specific vitals reading as FHIR WellnessRecord.
    Maps VitalReading model to FHIR Bundle.
    """
    try:
        # Fetch the reading
        reading = VitalReading.objects.select_related('patient', 'vital_type').get(id=vitals_id)
        
        # Initialize Adapter
        adapter = ABDMFHIRAdapter()
        
        patient = reading.patient
        patient_data = {
            'id': str(patient.id),
            'name': f"{patient.user.first_name} {patient.user.last_name}",
            'gender': patient.gender.lower() if patient.gender else 'unknown',
            'birth_date': getattr(patient, 'date_of_birth', None).strftime('%Y-%m-%d') if getattr(patient, 'date_of_birth', None) else None,
            'phone': patient.user.mobile_number if hasattr(patient.user, 'mobile_number') else getattr(patient, 'mobile_number', '1234567890'),
            'abha_id': patient.abha_address or patient.abha_number or (patient.abha_profile.abha_address if hasattr(patient, 'abha_profile') else None)
        }

        # 2. Map Vitals Data (Reading -> Dictionary)
        vitals_data = {}
        # We define a mapping based on VitalType code or name
        # Adapting to what we saw in existing models
        code = reading.vital_type.code.upper()
        
        if code in ['BP', 'BLOOD_PRESSURE']: 
             # Blood Pressure (Multi-value)
             systolic = reading.values.get('systolic')
             diastolic = reading.values.get('diastolic')
             if systolic and diastolic:
                 vitals_data['blood_pressure'] = {
                     'systolic': float(systolic),
                     'diastolic': float(diastolic)
                 }

        elif code in ['HR', 'HEART_RATE']:
             if reading.value:
                vitals_data['heart_rate'] = float(reading.value)

        elif code in ['SPO2', 'OXYGEN_SATURATION']:
             if reading.value:
                vitals_data['spo2'] = float(reading.value)

        elif code in ['TEMP', 'TEMPERATURE']:
             if reading.value:
                vitals_data['temperature'] = {
                    'value': float(reading.value),
                    'unit': str(reading.unit).replace('celsius', 'C').replace('fahrenheit', 'F').upper()[0] # simple mapping
                }

        elif code in ['RR', 'RESPIRATORY_RATE']:
             if reading.value:
                vitals_data['respiratory_rate'] = float(reading.value)

        # 3. Generate Bundle
        fhir_bundle = adapter.create_wellness_record_bundle(
            patient_data=patient_data,
            vitals_data=vitals_data,
            recorded_at=reading.measured_at
        )
        
        return Response({
            'success': True,
            'fhir_bundle': fhir_bundle,
            'bundle_id': fhir_bundle['id']
        })

    except VitalReading.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Vitals record not found'
        }, status=404)
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)
