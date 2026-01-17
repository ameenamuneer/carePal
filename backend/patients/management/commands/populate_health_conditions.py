from django.core.management.base import BaseCommand
from patients.models import HealthCondition

class Command(BaseCommand):
    help = 'Populates the database with initial health conditions'

    def handle(self, *args, **kwargs):
        conditions = [
            {'name': 'Hypertension', 'category': 'CARDIOVASCULAR', 'description': 'High blood pressure'},
            {'name': 'Diabetes Type 2', 'category': 'ENDOCRINE', 'description': 'Type 2 diabetes mellitus'},
            {'name': 'COPD', 'category': 'RESPIRATORY', 'description': 'Chronic Obstructive Pulmonary Disease'},
            {'name': 'Arthritis', 'category': 'MUSCULOSKELETAL', 'description': 'Joint inflammation'},
            {'name': 'Chronic Kidney Disease', 'category': 'RENAL', 'description': 'Long-standing kidney disease'},
            {'name': 'Heart Failure', 'category': 'CARDIOVASCULAR', 'description': 'Heart inability to pump blood'},
            {'name': 'Asthma', 'category': 'RESPIRATORY', 'description': 'Airway inflammation'},
            {'name': 'Depression', 'category': 'MENTAL', 'description': 'Mood disorder'},
            {'name': 'Anxiety', 'category': 'MENTAL', 'description': 'Generalized anxiety disorder'},
            {'name': 'Migraine', 'category': 'NEUROLOGICAL', 'description': 'Severe headache'},
        ]
        
        created_count = 0
        for cond in conditions:
            obj, created = HealthCondition.objects.get_or_create(
                name=cond['name'],
                defaults={
                    'category': cond['category'],
                    'description': cond.get('description', '')
                }
            )
            if created:
                created_count += 1
                
        self.stdout.write(self.style.SUCCESS(f'Health conditions populated. Created {created_count} new conditions.'))
