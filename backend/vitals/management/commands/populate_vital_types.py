from django.core.management.base import BaseCommand
from vitals.models import VitalType


class Command(BaseCommand):
    help = 'Populate vital types catalog with common vitals'
    
    def handle(self, *args, **kwargs):
        vital_types = [
            {
                'name': 'Blood Pressure',
                'code': 'BP',
                'category': 'CARDIOVASCULAR',
                'unit': 'mmHg',
                'description': 'Systolic and diastolic blood pressure',
                'requires_multiple_values': True,
                'is_continuous': False,
                'normal_range': {
                    'systolic': {'min': 90, 'max': 120, 'critical_low': 80, 'critical_high': 180},
                    'diastolic': {'min': 60, 'max': 80, 'critical_low': 50, 'critical_high': 120}
                }
            },
            {
                'name': 'Heart Rate',
                'code': 'HR',
                'category': 'CARDIOVASCULAR',
                'unit': 'bpm',
                'description': 'Heart beats per minute',
                'requires_multiple_values': False,
                'is_continuous': True,
                'normal_range': {
                    'min': 60, 'max': 100, 'critical_low': 40, 'critical_high': 120
                }
            },
            {
                'name': 'Oxygen Saturation',
                'code': 'SPO2',
                'category': 'RESPIRATORY',
                'unit': 'percent',
                'description': 'Blood oxygen saturation level',
                'requires_multiple_values': False,
                'is_continuous': True,
                'normal_range': {
                    'min': 95, 'max': 100, 'critical_low': 90, 'critical_high': 100
                }
            },
            {
                'name': 'Body Temperature',
                'code': 'TEMP',
                'category': 'BODY',
                'unit': 'celsius',
                'description': 'Core body temperature',
                'requires_multiple_values': False,
                'is_continuous': False,
                'normal_range': {
                    'min': 36.1, 'max': 37.2, 'critical_low': 35.0, 'critical_high': 39.0
                }
            },
            {
                'name': 'Blood Glucose',
                'code': 'GLUCOSE',
                'category': 'METABOLIC',
                'unit': 'mg_dl',
                'description': 'Blood sugar level',
                'requires_multiple_values': False,
                'is_continuous': False,
                'normal_range': {
                    'min': 70, 'max': 100, 'critical_low': 54, 'critical_high': 200
                }
            },
            {
                'name': 'Respiratory Rate',
                'code': 'RR',
                'category': 'RESPIRATORY',
                'unit': 'breaths_min',
                'description': 'Breaths per minute',
                'requires_multiple_values': False,
                'is_continuous': True,
                'normal_range': {
                    'min': 12, 'max': 20, 'critical_low': 8, 'critical_high': 30
                }
            },
            {
                'name': 'Weight',
                'code': 'WEIGHT',
                'category': 'BODY',
                'unit': 'kg',
                'description': 'Body weight',
                'requires_multiple_values': False,
                'is_continuous': False,
                'normal_range': {}
            },
            {
                'name': 'Steps',
                'code': 'STEPS',
                'category': 'PHYSICAL',
                'unit': 'steps',
                'description': 'Daily step count',
                'requires_multiple_values': False,
                'is_continuous': True,
                'normal_range': {}
            },
            {
                'name': 'Sleep Duration',
                'code': 'SLEEP',
                'category': 'PHYSICAL',
                'unit': 'hours',
                'description': 'Hours of sleep',
                'requires_multiple_values': False,
                'is_continuous': False,
                'normal_range': {
                    'min': 7, 'max': 9, 'critical_low': 4, 'critical_high': 12
                }
            }
        ]
        
        created_count = 0
        updated_count = 0
        
        for vt_data in vital_types:
            vital_type, created = VitalType.objects.update_or_create(
                code=vt_data['code'],
                defaults=vt_data
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Created: {vital_type.name}')
                )
            else:
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f'Updated: {vital_type.name}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\nCompleted: {created_count} created, {updated_count} updated'
            )
        )
