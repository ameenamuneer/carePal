"""
CarePAL ABDM FHIR Adapter
Converts CarePAL vitals data to ABDM FHIR WellnessRecord format

This adapter transforms CarePAL's internal vitals data model into
FHIR R4 compliant WellnessRecord bundles following ABDM specifications.

Reference: https://nrces.in/ndhm/fhir/r4/StructureDefinition-WellnessRecord.html
"""

import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
import json


class ABDMFHIRAdapter:
    """
    Adapter to convert CarePAL vitals data to ABDM FHIR WellnessRecord format.
    
    Supports conversion of:
    - Blood Pressure (Systolic/Diastolic)
    - Heart Rate (BPM)
    - SpO2 (Oxygen Saturation)
    - Temperature (Celsius/Fahrenheit)
    - Respiratory Rate
    - Body Weight
    - Body Height
    """
    
    # LOINC Codes for Vital Signs (Standard medical terminology)
    LOINC_CODES = {
        'blood_pressure_panel': '85354-9',
        'systolic_bp': '8480-6',
        'diastolic_bp': '8462-4',
        'heart_rate': '8867-4',
        'spo2': '2708-6',
        'body_temperature': '8310-5',
        'respiratory_rate': '9279-1',
        'body_weight': '29463-7',
        'body_height': '8302-2',
        'bmi': '39156-5'
    }
    
    # SNOMED-CT Codes for body sites
    SNOMED_BODY_SITES = {
        'right_arm': '368209003',
        'left_arm': '368208006',
        'oral': '123851003',
        'axillary': '91470000'
    }
    
    def __init__(self, facility_info: Optional[Dict] = None):
        """
        Initialize the FHIR adapter.
        
        Args:
            facility_info: Optional facility/organization details
        """
        self.facility_info = facility_info or {
            'id': 'carepal-facility-001',
            'name': 'CarePAL Health Services',
            'identifier': 'CAREPAL001',
            'telecom': {
                'phone': '+91-XXXXXXXXXX',
                'email': 'support@carepal.health'
            }
        }
    
    def generate_uuid(self) -> str:
        """Generate a UUID for FHIR resources."""
        return str(uuid.uuid4())
    
    def format_datetime(self, dt: Optional[datetime] = None) -> str:
        """
        Format datetime to FHIR dateTime format (ISO 8601).
        
        Args:
            dt: DateTime object (defaults to current time)
        
        Returns:
            ISO 8601 formatted datetime string
        """
        if dt is None:
            dt = datetime.now()
        return dt.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + '+05:30'
    
    def create_patient_resource(self, patient_data: Dict) -> Dict:
        """
        Create FHIR Patient resource from CarePAL patient data.
        
        Expected patient_data structure:
        {
            'id': 'patient-uuid',
            'name': 'Patient Name',
            'gender': 'male/female/other',
            'birth_date': '1950-01-15',
            'phone': '+91XXXXXXXXXX',
            'abha_id': 'XX-XXXX-XXXX-XXXX' (optional)
        }
        """
        patient_id = patient_data.get('id', self.generate_uuid())
        
        patient = {
            'resourceType': 'Patient',
            'id': patient_id,
            'meta': {
                'versionId': '1',
                'lastUpdated': self.format_datetime(),
                'profile': ['https://nrces.in/ndhm/fhir/r4/StructureDefinition/Patient']
            },
            'identifier': [],
            'name': [{
                'text': patient_data.get('name', 'Unknown Patient')
            }],
            'gender': patient_data.get('gender', 'unknown'),
        }
        
        # Add ABHA ID if available
        if patient_data.get('abha_id'):
            patient['identifier'].append({
                'type': {
                    'coding': [{
                        'system': 'http://terminology.hl7.org/CodeSystem/v2-0203',
                        'code': 'MR',
                        'display': 'Medical record number'
                    }]
                },
                'system': 'https://healthid.ndhm.gov.in',
                'value': patient_data['abha_id']
            })
        
        # Add birth date if available
        if patient_data.get('birth_date'):
            patient['birthDate'] = patient_data['birth_date']
        
        # Add phone number if available
        if patient_data.get('phone'):
            patient['telecom'] = [{
                'system': 'phone',
                'value': patient_data['phone'],
                'use': 'home'
            }]
        
        return patient
    
    def create_practitioner_resource(self, practitioner_data: Optional[Dict] = None) -> Dict:
        """
        Create FHIR Practitioner resource.
        
        For CarePAL, this could be the device/system or actual healthcare provider.
        """
        practitioner_id = self.generate_uuid()
        
        if practitioner_data is None:
            # Default: CarePAL AI System
            practitioner_data = {
                'name': 'CarePAL AI System',
                'qualification': 'Automated Health Monitoring System'
            }
        
        return {
            'resourceType': 'Practitioner',
            'id': practitioner_id,
            'meta': {
                'profile': ['https://nrces.in/ndhm/fhir/r4/StructureDefinition/Practitioner']
            },
            'identifier': [{
                'system': 'https://carepal.health/practitioners',
                'value': practitioner_id
            }],
            'name': [{
                'text': practitioner_data.get('name', 'CarePAL System')
            }]
        }
    
    def create_organization_resource(self) -> Dict:
        """Create FHIR Organization resource for CarePAL facility."""
        org_id = self.generate_uuid()
        
        return {
            'resourceType': 'Organization',
            'id': org_id,
            'meta': {
                'profile': ['https://nrces.in/ndhm/fhir/r4/StructureDefinition/Organization']
            },
            'identifier': [{
                'type': {
                    'coding': [{
                        'system': 'http://terminology.hl7.org/CodeSystem/v2-0203',
                        'code': 'PRN',
                        'display': 'Provider number'
                    }]
                },
                'system': 'https://facility.ndhm.gov.in',
                'value': self.facility_info['identifier']
            }],
            'name': self.facility_info['name'],
            'telecom': [
                {
                    'system': 'phone',
                    'value': self.facility_info['telecom']['phone'],
                    'use': 'work'
                },
                {
                    'system': 'email',
                    'value': self.facility_info['telecom']['email'],
                    'use': 'work'
                }
            ]
        }
    
    def create_blood_pressure_observation(
        self,
        systolic: float,
        diastolic: float,
        patient_ref: str,
        practitioner_ref: str,
        recorded_at: Optional[datetime] = None,
        body_site: str = 'right_arm'
    ) -> Dict:
        """
        Create FHIR Observation for Blood Pressure.
        
        Args:
            systolic: Systolic BP in mmHg
            diastolic: Diastolic BP in mmHg
            patient_ref: Reference to patient resource
            practitioner_ref: Reference to practitioner resource
            recorded_at: DateTime when measurement was taken
            body_site: Body site where measurement was taken
        """
        obs_id = self.generate_uuid()
        effective_datetime = self.format_datetime(recorded_at)
        
        # Interpretation based on standard BP ranges
        interpretation = self._interpret_blood_pressure(systolic, diastolic)
        
        observation = {
            'resourceType': 'Observation',
            'id': obs_id,
            'meta': {
                'profile': [
                    'https://nrces.in/ndhm/fhir/r4/StructureDefinition/Observation',
                    'https://nrces.in/ndhm/fhir/r4/StructureDefinition/ObservationVitalSigns'
                ]
            },
            'identifier': [{
                'system': 'https://carepal.health/observations',
                'value': f'urn:uuid:{obs_id}'
            }],
            'status': 'final',
            'category': [{
                'coding': [{
                    'system': 'http://terminology.hl7.org/CodeSystem/observation-category',
                    'code': 'vital-signs',
                    'display': 'Vital Signs'
                }]
            }],
            'code': {
                'coding': [{
                    'system': 'http://loinc.org',
                    'code': self.LOINC_CODES['blood_pressure_panel'],
                    'display': 'Blood pressure panel with all children optional'
                }],
                'text': 'Blood Pressure'
            },
            'subject': {
                'reference': patient_ref
            },
            'effectiveDateTime': effective_datetime,
            'performer': [{
                'reference': practitioner_ref
            }],
            'interpretation': [{
                'coding': [{
                    'system': 'http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation',
                    'code': interpretation['code'],
                    'display': interpretation['display']
                }]
            }],
            'bodySite': {
                'coding': [{
                    'system': 'http://snomed.info/sct',
                    'code': self.SNOMED_BODY_SITES.get(body_site, self.SNOMED_BODY_SITES['right_arm']),
                    'display': body_site.replace('_', ' ').title()
                }]
            },
            'component': [
                {
                    'code': {
                        'coding': [{
                            'system': 'http://loinc.org',
                            'code': self.LOINC_CODES['systolic_bp'],
                            'display': 'Systolic blood pressure'
                        }]
                    },
                    'valueQuantity': {
                        'value': systolic,
                        'unit': 'mmHg',
                        'system': 'http://unitsofmeasure.org',
                        'code': 'mm[Hg]'
                    }
                },
                {
                    'code': {
                        'coding': [{
                            'system': 'http://loinc.org',
                            'code': self.LOINC_CODES['diastolic_bp'],
                            'display': 'Diastolic blood pressure'
                        }]
                    },
                    'valueQuantity': {
                        'value': diastolic,
                        'unit': 'mmHg',
                        'system': 'http://unitsofmeasure.org',
                        'code': 'mm[Hg]'
                    }
                }
            ]
        }
        
        return observation
    
    def create_heart_rate_observation(
        self,
        heart_rate: float,
        patient_ref: str,
        practitioner_ref: str,
        recorded_at: Optional[datetime] = None
    ) -> Dict:
        """Create FHIR Observation for Heart Rate."""
        obs_id = self.generate_uuid()
        effective_datetime = self.format_datetime(recorded_at)
        
        interpretation = self._interpret_heart_rate(heart_rate)
        
        return {
            'resourceType': 'Observation',
            'id': obs_id,
            'meta': {
                'profile': [
                    'https://nrces.in/ndhm/fhir/r4/StructureDefinition/Observation',
                    'https://nrces.in/ndhm/fhir/r4/StructureDefinition/ObservationVitalSigns'
                ]
            },
            'identifier': [{
                'system': 'https://carepal.health/observations',
                'value': f'urn:uuid:{obs_id}'
            }],
            'status': 'final',
            'category': [{
                'coding': [{
                    'system': 'http://terminology.hl7.org/CodeSystem/observation-category',
                    'code': 'vital-signs',
                    'display': 'Vital Signs'
                }]
            }],
            'code': {
                'coding': [{
                    'system': 'http://loinc.org',
                    'code': self.LOINC_CODES['heart_rate'],
                    'display': 'Heart rate'
                }],
                'text': 'Heart Rate'
            },
            'subject': {
                'reference': patient_ref
            },
            'effectiveDateTime': effective_datetime,
            'performer': [{
                'reference': practitioner_ref
            }],
            'valueQuantity': {
                'value': heart_rate,
                'unit': 'beats/minute',
                'system': 'http://unitsofmeasure.org',
                'code': '/min'
            },
            'interpretation': [{
                'coding': [{
                    'system': 'http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation',
                    'code': interpretation['code'],
                    'display': interpretation['display']
                }]
            }]
        }
    
    def create_spo2_observation(
        self,
        spo2: float,
        patient_ref: str,
        practitioner_ref: str,
        recorded_at: Optional[datetime] = None
    ) -> Dict:
        """Create FHIR Observation for SpO2 (Oxygen Saturation)."""
        obs_id = self.generate_uuid()
        effective_datetime = self.format_datetime(recorded_at)
        
        interpretation = self._interpret_spo2(spo2)
        
        return {
            'resourceType': 'Observation',
            'id': obs_id,
            'meta': {
                'profile': [
                    'https://nrces.in/ndhm/fhir/r4/StructureDefinition/Observation',
                    'https://nrces.in/ndhm/fhir/r4/StructureDefinition/ObservationVitalSigns'
                ]
            },
            'identifier': [{
                'system': 'https://carepal.health/observations',
                'value': f'urn:uuid:{obs_id}'
            }],
            'status': 'final',
            'category': [{
                'coding': [{
                    'system': 'http://terminology.hl7.org/CodeSystem/observation-category',
                    'code': 'vital-signs',
                    'display': 'Vital Signs'
                }]
            }],
            'code': {
                'coding': [{
                    'system': 'http://loinc.org',
                    'code': self.LOINC_CODES['spo2'],
                    'display': 'Oxygen saturation in Arterial blood by Pulse oximetry'
                }],
                'text': 'SpO2'
            },
            'subject': {
                'reference': patient_ref
            },
            'effectiveDateTime': effective_datetime,
            'performer': [{
                'reference': practitioner_ref
            }],
            'valueQuantity': {
                'value': spo2,
                'unit': '%',
                'system': 'http://unitsofmeasure.org',
                'code': '%'
            },
            'interpretation': [{
                'coding': [{
                    'system': 'http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation',
                    'code': interpretation['code'],
                    'display': interpretation['display']
                }]
            }]
        }
    
    def create_temperature_observation(
        self,
        temperature: float,
        unit: str,
        patient_ref: str,
        practitioner_ref: str,
        recorded_at: Optional[datetime] = None,
        body_site: str = 'oral'
    ) -> Dict:
        """
        Create FHIR Observation for Body Temperature.
        
        Args:
            temperature: Temperature value
            unit: 'C' for Celsius or 'F' for Fahrenheit
            body_site: 'oral', 'axillary', etc.
        """
        obs_id = self.generate_uuid()
        effective_datetime = self.format_datetime(recorded_at)
        
        # Convert to Celsius if Fahrenheit
        temp_celsius = temperature if unit == 'C' else (temperature - 32) * 5/9
        interpretation = self._interpret_temperature(temp_celsius)
        
        unit_code = 'Cel' if unit == 'C' else '[degF]'
        unit_display = '°C' if unit == 'C' else '°F'
        
        return {
            'resourceType': 'Observation',
            'id': obs_id,
            'meta': {
                'profile': [
                    'https://nrces.in/ndhm/fhir/r4/StructureDefinition/Observation',
                    'https://nrces.in/ndhm/fhir/r4/StructureDefinition/ObservationVitalSigns'
                ]
            },
            'identifier': [{
                'system': 'https://carepal.health/observations',
                'value': f'urn:uuid:{obs_id}'
            }],
            'status': 'final',
            'category': [{
                'coding': [{
                    'system': 'http://terminology.hl7.org/CodeSystem/observation-category',
                    'code': 'vital-signs',
                    'display': 'Vital Signs'
                }]
            }],
            'code': {
                'coding': [{
                    'system': 'http://loinc.org',
                    'code': self.LOINC_CODES['body_temperature'],
                    'display': 'Body temperature'
                }],
                'text': 'Body Temperature'
            },
            'subject': {
                'reference': patient_ref
            },
            'effectiveDateTime': effective_datetime,
            'performer': [{
                'reference': practitioner_ref
            }],
            'valueQuantity': {
                'value': temperature,
                'unit': unit_display,
                'system': 'http://unitsofmeasure.org',
                'code': unit_code
            },
            'interpretation': [{
                'coding': [{
                    'system': 'http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation',
                    'code': interpretation['code'],
                    'display': interpretation['display']
                }]
            }],
            'bodySite': {
                'coding': [{
                    'system': 'http://snomed.info/sct',
                    'code': self.SNOMED_BODY_SITES.get(body_site, self.SNOMED_BODY_SITES['oral']),
                    'display': body_site.title()
                }]
            }
        }
    
    def create_respiratory_rate_observation(
        self,
        respiratory_rate: float,
        patient_ref: str,
        practitioner_ref: str,
        recorded_at: Optional[datetime] = None
    ) -> Dict:
        """Create FHIR Observation for Respiratory Rate."""
        obs_id = self.generate_uuid()
        effective_datetime = self.format_datetime(recorded_at)
        
        interpretation = self._interpret_respiratory_rate(respiratory_rate)
        
        return {
            'resourceType': 'Observation',
            'id': obs_id,
            'meta': {
                'profile': [
                    'https://nrces.in/ndhm/fhir/r4/StructureDefinition/Observation',
                    'https://nrces.in/ndhm/fhir/r4/StructureDefinition/ObservationVitalSigns'
                ]
            },
            'identifier': [{
                'system': 'https://carepal.health/observations',
                'value': f'urn:uuid:{obs_id}'
            }],
            'status': 'final',
            'category': [{
                'coding': [{
                    'system': 'http://terminology.hl7.org/CodeSystem/observation-category',
                    'code': 'vital-signs',
                    'display': 'Vital Signs'
                }]
            }],
            'code': {
                'coding': [{
                    'system': 'http://loinc.org',
                    'code': self.LOINC_CODES['respiratory_rate'],
                    'display': 'Respiratory rate'
                }],
                'text': 'Respiratory Rate'
            },
            'subject': {
                'reference': patient_ref
            },
            'effectiveDateTime': effective_datetime,
            'performer': [{
                'reference': practitioner_ref
            }],
            'valueQuantity': {
                'value': respiratory_rate,
                'unit': 'breaths/minute',
                'system': 'http://unitsofmeasure.org',
                'code': '/min'
            },
            'interpretation': [{
                'coding': [{
                    'system': 'http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation',
                    'code': interpretation['code'],
                    'display': interpretation['display']
                }]
            }]
        }
    
    def create_composition_resource(
        self,
        patient_ref: str,
        practitioner_ref: str,
        organization_ref: str,
        vital_signs_refs: List[str],
        body_measurement_refs: Optional[List[str]] = None,
        recorded_at: Optional[datetime] = None
    ) -> Dict:
        """
        Create FHIR Composition resource - the main document structure.
        
        Args:
            patient_ref: Reference to patient resource
            practitioner_ref: Reference to practitioner resource
            organization_ref: Reference to organization resource
            vital_signs_refs: List of references to vital sign observations
            body_measurement_refs: Optional list of references to body measurement observations
            recorded_at: DateTime when the document was created
        """
        composition_id = self.generate_uuid()
        composition_date = self.format_datetime(recorded_at)
        
        composition = {
            'resourceType': 'Composition',
            'id': composition_id,
            'meta': {
                'versionId': '1',
                'lastUpdated': composition_date,
                'profile': ['https://nrces.in/ndhm/fhir/r4/StructureDefinition/WellnessRecord']
            },
            'language': 'en-IN',
            'identifier': {
                'system': 'https://carepal.health/wellness-records',
                'value': composition_id
            },
            'status': 'final',
            'type': {
                'coding': [{
                    'system': 'http://snomed.info/sct',
                    'code': '371525003',
                    'display': 'Clinical procedure report'
                }],
                'text': 'Wellness Record'
            },
            'subject': {
                'reference': patient_ref
            },
            'date': composition_date,
            'author': [{
                'reference': practitioner_ref
            }],
            'title': 'CarePAL Wellness Record',
            'custodian': {
                'reference': organization_ref
            },
            'section': []
        }
        
        # Add Vital Signs section
        if vital_signs_refs:
            composition['section'].append({
                'title': 'Vital Signs',
                'code': {
                    'coding': [{
                        'system': 'http://snomed.info/sct',
                        'code': '118227000',
                        'display': 'Vital signs finding'
                    }]
                },
                'entry': [{'reference': ref} for ref in vital_signs_refs]
            })
        
        # Add Body Measurement section if available
        if body_measurement_refs:
            composition['section'].append({
                'title': 'Body Measurement',
                'code': {
                    'coding': [{
                        'system': 'http://snomed.info/sct',
                        'code': '248326004',
                        'display': 'Body measure'
                    }]
                },
                'entry': [{'reference': ref} for ref in body_measurement_refs]
            })
        
        return composition
    
    def create_wellness_record_bundle(
        self,
        patient_data: Dict,
        vitals_data: Dict,
        practitioner_data: Optional[Dict] = None,
        recorded_at: Optional[datetime] = None
    ) -> Dict:
        """
        Create complete ABDM FHIR WellnessRecord Bundle.
        
        Args:
            patient_data: Patient information dict
            vitals_data: Dictionary containing vitals measurements:
                {
                    'blood_pressure': {'systolic': 120, 'diastolic': 80},
                    'heart_rate': 72,
                    'spo2': 98,
                    'temperature': {'value': 37.0, 'unit': 'C'},
                    'respiratory_rate': 16
                }
            practitioner_data: Optional practitioner information
            recorded_at: DateTime when vitals were recorded
        
        Returns:
            Complete FHIR Bundle in JSON format
        """
        bundle_id = self.generate_uuid()
        timestamp = self.format_datetime(recorded_at)
        
        # Create resources
        patient = self.create_patient_resource(patient_data)
        practitioner = self.create_practitioner_resource(practitioner_data)
        organization = self.create_organization_resource()
        
        patient_ref = f"urn:uuid:{patient['id']}"
        practitioner_ref = f"urn:uuid:{practitioner['id']}"
        organization_ref = f"urn:uuid:{organization['id']}"
        
        # Create vital sign observations
        vital_observations = []
        vital_refs = []
        
        # Blood Pressure
        if 'blood_pressure' in vitals_data:
            bp_data = vitals_data['blood_pressure']
            bp_obs = self.create_blood_pressure_observation(
                systolic=bp_data['systolic'],
                diastolic=bp_data['diastolic'],
                patient_ref=patient_ref,
                practitioner_ref=practitioner_ref,
                recorded_at=recorded_at
            )
            vital_observations.append(bp_obs)
            vital_refs.append(f"urn:uuid:{bp_obs['id']}")
        
        # Heart Rate
        if 'heart_rate' in vitals_data:
            hr_obs = self.create_heart_rate_observation(
                heart_rate=vitals_data['heart_rate'],
                patient_ref=patient_ref,
                practitioner_ref=practitioner_ref,
                recorded_at=recorded_at
            )
            vital_observations.append(hr_obs)
            vital_refs.append(f"urn:uuid:{hr_obs['id']}")
        
        # SpO2
        if 'spo2' in vitals_data:
            spo2_obs = self.create_spo2_observation(
                spo2=vitals_data['spo2'],
                patient_ref=patient_ref,
                practitioner_ref=practitioner_ref,
                recorded_at=recorded_at
            )
            vital_observations.append(spo2_obs)
            vital_refs.append(f"urn:uuid:{spo2_obs['id']}")
        
        # Temperature
        if 'temperature' in vitals_data:
            temp_data = vitals_data['temperature']
            temp_obs = self.create_temperature_observation(
                temperature=temp_data['value'],
                unit=temp_data.get('unit', 'C'),
                patient_ref=patient_ref,
                practitioner_ref=practitioner_ref,
                recorded_at=recorded_at
            )
            vital_observations.append(temp_obs)
            vital_refs.append(f"urn:uuid:{temp_obs['id']}")
        
        # Respiratory Rate
        if 'respiratory_rate' in vitals_data:
            rr_obs = self.create_respiratory_rate_observation(
                respiratory_rate=vitals_data['respiratory_rate'],
                patient_ref=patient_ref,
                practitioner_ref=practitioner_ref,
                recorded_at=recorded_at
            )
            vital_observations.append(rr_obs)
            vital_refs.append(f"urn:uuid:{rr_obs['id']}")
        
        # Create Composition
        composition = self.create_composition_resource(
            patient_ref=patient_ref,
            practitioner_ref=practitioner_ref,
            organization_ref=organization_ref,
            vital_signs_refs=vital_refs,
            recorded_at=recorded_at
        )
        
        # Build Bundle
        bundle = {
            'resourceType': 'Bundle',
            'id': bundle_id,
            'meta': {
                'versionId': '1',
                'lastUpdated': timestamp,
                'profile': ['https://nrces.in/ndhm/fhir/r4/StructureDefinition/DocumentBundle'],
                'security': [{
                    'system': 'http://terminology.hl7.org/CodeSystem/v3-Confidentiality',
                    'code': 'V',
                    'display': 'very restricted'
                }]
            },
            'identifier': {
                'system': 'https://carepal.health',
                'value': bundle_id
            },
            'type': 'document',
            'timestamp': timestamp,
            'entry': [
                {
                    'fullUrl': f"urn:uuid:{composition['id']}",
                    'resource': composition
                },
                {
                    'fullUrl': patient_ref,
                    'resource': patient
                },
                {
                    'fullUrl': practitioner_ref,
                    'resource': practitioner
                },
                {
                    'fullUrl': organization_ref,
                    'resource': organization
                }
            ]
        }
        
        # Add vital sign observations to bundle
        for obs in vital_observations:
            bundle['entry'].append({
                'fullUrl': f"urn:uuid:{obs['id']}",
                'resource': obs
            })
        
        return bundle
    
    # Helper methods for clinical interpretation
    
    def _interpret_blood_pressure(self, systolic: float, diastolic: float) -> Dict:
        """Interpret blood pressure reading."""
        if systolic < 90 or diastolic < 60:
            return {'code': 'L', 'display': 'Below low normal'}
        elif systolic >= 140 or diastolic >= 90:
            return {'code': 'H', 'display': 'Above high normal'}
        elif systolic >= 120 or diastolic >= 80:
            return {'code': 'N', 'display': 'Normal'}
        else:
            return {'code': 'N', 'display': 'Normal'}
    
    def _interpret_heart_rate(self, heart_rate: float) -> Dict:
        """Interpret heart rate reading."""
        if heart_rate < 60:
            return {'code': 'L', 'display': 'Below low normal'}
        elif heart_rate > 100:
            return {'code': 'H', 'display': 'Above high normal'}
        else:
            return {'code': 'N', 'display': 'Normal'}
    
    def _interpret_spo2(self, spo2: float) -> Dict:
        """Interpret SpO2 reading."""
        if spo2 < 90:
            return {'code': 'LL', 'display': 'Critically low'}
        elif spo2 < 95:
            return {'code': 'L', 'display': 'Below low normal'}
        else:
            return {'code': 'N', 'display': 'Normal'}
    
    def _interpret_temperature(self, temp_celsius: float) -> Dict:
        """Interpret temperature reading (in Celsius)."""
        if temp_celsius < 36.1:
            return {'code': 'L', 'display': 'Below low normal'}
        elif temp_celsius > 37.2:
            return {'code': 'H', 'display': 'Above high normal'}
        else:
            return {'code': 'N', 'display': 'Normal'}
    
    def _interpret_respiratory_rate(self, rr: float) -> Dict:
        """Interpret respiratory rate reading."""
        if rr < 12:
            return {'code': 'L', 'display': 'Below low normal'}
        elif rr > 20:
            return {'code': 'H', 'display': 'Above high normal'}
        else:
            return {'code': 'N', 'display': 'Normal'}
