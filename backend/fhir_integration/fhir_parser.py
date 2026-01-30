
import logging
from typing import Dict, List, Optional
from datetime import datetime
from dateutil.parser import parse

logger = logging.getLogger(__name__)

class FHIRToCarePalParser:
    """
    Parses FHIR R4 Bundles (Wellness Records) into CarePAL Vital Readings.
    """

    LOINC_MAP = {
        '85354-9': 'BP',    # Blood Pressure Panel
        '8867-4':  'HR',    # Heart Rate
        '2708-6':  'SPO2',  # SpO2
        '8310-5':  'TEMP',  # Body Temperature
        '9279-1':  'RESP',  # Respiratory Rate
    }

    def parse_bundle(self, bundle_json: Dict) -> List[Dict]:
        """
        Parse a FHIR Bundle JSON string/dict and return list of reading dicts
        ready for the CarePAL internal API or database.
        """
        readings = []
        
        if not bundle_json or 'entry' not in bundle_json:
            return readings

        entries = bundle_json.get('entry', [])
        
        for entry in entries:
            resource = entry.get('resource', {})
            res_type = resource.get('resourceType')
            
            if res_type == 'Observation':
                reading = self._parse_observation(resource)
                if reading:
                    readings.append(reading)
        
        logger.info(f"Parserd {len(readings)} vitals from FHIR Bundle")
        return readings

    def _parse_observation(self, observation: Dict) -> Optional[Dict]:
        """Extract vital data from Observation resource"""
        try:
            # 1. Identify Vital Type via LOINC
            code_entry = observation.get('code', {}).get('coding', [])
            vital_type = 'UNKNOWN'
            
            for coding in code_entry:
                system = coding.get('system', '')
                code = coding.get('code', '')
                if 'loinc.org' in system and code in self.LOINC_MAP:
                    vital_type = self.LOINC_MAP[code]
                    break
            
            if vital_type == 'UNKNOWN':
                return None # Skip unknown observations
            
            # 2. Extract Value/Components
            value = 0.0
            values = {}
            unit = ''

            # Blood Pressure (Compound)
            if vital_type == 'BP':
                components = observation.get('component', [])
                systolic = 0.0
                diastolic = 0.0
                
                for comp in components:
                    c_code = comp.get('code', {}).get('coding', [{}])[0].get('code')
                    val = comp.get('valueQuantity', {}).get('value')
                    
                    if c_code == '8480-6': # Systolic
                        systolic = float(val)
                    elif c_code == '8462-4': # Diastolic
                        diastolic = float(val)
                
                values = {
                    'systolic': systolic,
                    'diastolic': diastolic
                }
                value = systolic # Primary value usually systolic for sorting
                unit = 'mmHg'

            # Simple Vitals (HR, SpO2, Temp)
            else:
                val_qty = observation.get('valueQuantity')
                if val_qty:
                    value = float(val_qty.get('value', 0.0))
                    unit = val_qty.get('unit', '')
                else:
                    return None # No value found

            # 3. Extract Timestamp
            effective_dt = observation.get('effectiveDateTime')
            measured_at = datetime.now()
            if effective_dt:
                measured_at = parse(effective_dt)
            
            # 4. Construct Result
            return {
                'vital_type': vital_type,
                'value': value,
                'values': values if values else None,
                'unit': unit,
                'measured_at': measured_at,
                'notes': f"Imported from ABDM (FHIR ID: {observation.get('id')})"
            }

        except Exception as e:
            logger.error(f"Error parsing observation: {e}")
            return None
