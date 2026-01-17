from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta, time
from users.models import User
from patients.models import PatientProfile
from medications.models import Medication, MedicationSchedule
from medications.tasks import generate_adherence_records

class Command(BaseCommand):
    help = 'Populates the database with sample medication data'

    def handle(self, *args, **kwargs):
        self.stdout.write('Populating medications data...')

        # Ensure we have a patient
        user, created = User.objects.get_or_create(
            email='testpatient@example.com',
            defaults={
                'username': 'testpatient',
                'first_name': 'Test',
                'last_name': 'Patient',
                'user_type': 'PATIENT',
                'is_active': True
            }
        )
        if created:
            user.set_password('password123')
            user.save()
            self.stdout.write(f'Created user: {user.email}')

        patient, created = PatientProfile.objects.get_or_create(
            user=user,
            defaults={
                'gender': 'M',
                'blood_group': 'O+'
            }
        )
        if created:
            self.stdout.write(f'Created patient profile for: {user.email}')

        # Create Medications
        medications_data = [
            {
                'medication_name': 'Lisinopril',
                'start_date': timezone.now().date(),
                'dosage': '10mg',
                'frequency': 'DAILY',
                'form': 'TABLET',
                'instructions': 'Take one tablet daily in the morning',
                'purpose': 'Blood Pressure',
                'is_critical': True,
                'quantity_prescribed': 30,
                'quantity_remaining': 30,
                'schedules': [
                    {'time': time(8, 0), 'label': 'Morning', 'food': False}
                ]
            },
            {
                'medication_name': 'Metformin',
                'start_date': timezone.now().date(),
                'dosage': '500mg',
                'frequency': 'TWICE_DAILY',
                'form': 'TABLET',
                'instructions': 'Take with meals',
                'purpose': 'Diabetes',
                'is_critical': True,
                'quantity_prescribed': 60,
                'quantity_remaining': 60,
                'schedules': [
                    {'time': time(8, 0), 'label': 'Breakfast', 'food': True},
                    {'time': time(20, 0), 'label': 'Dinner', 'food': True}
                ]
            },
            {
                'medication_name': 'Multivitamin',
                'start_date': timezone.now().date(),
                'dosage': '1 tablet',
                'frequency': 'DAILY',
                'form': 'TABLET',
                'instructions': 'Take with food',
                'purpose': 'Supplement',
                'is_critical': False,
                'quantity_prescribed': 90,
                'quantity_remaining': 90,
                'schedules': [
                    {'time': time(12, 0), 'label': 'Lunch', 'food': True}
                ]
            }
        ]

        for med_data in medications_data:
            schedules_data = med_data.pop('schedules')
            
            med, created = Medication.objects.get_or_create(
                patient=patient,
                medication_name=med_data['medication_name'],
                defaults=med_data
            )
            
            if created:
                self.stdout.write(f'Created medication: {med.medication_name}')
                
                # Create schedules
                for sch in schedules_data:
                    MedicationSchedule.objects.create(
                        medication=med,
                        time_of_day=sch['time'],
                        time_label=sch['label'],
                        with_food=sch['food']
                    )
                
                # Generate adherence records
                self.stdout.write(f'Generating adherence records for {med.medication_name}...')
                generate_adherence_records(med.id, days=7)
            else:
                self.stdout.write(f'Medication already exists: {med.medication_name}')

        self.stdout.write(self.style.SUCCESS('Successfully populated medications'))
