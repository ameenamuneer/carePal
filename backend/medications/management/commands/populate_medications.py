from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from users.models import User
from patients.models import PatientProfile
from medications.models import Medication
from medications.schedule_utils import default_dose_times_for_frequency

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
            }
        ]

        for med_data in medications_data:
            med, created = Medication.objects.get_or_create(
                patient=patient,
                medication_name=med_data['medication_name'],
                defaults=med_data
            )

            if created:
                # Auto-populate dose_times from frequency
                med.dose_times = default_dose_times_for_frequency(med.frequency)
                med.save(update_fields=['dose_times'])
                self.stdout.write(f'Created medication: {med.medication_name}')
            else:
                self.stdout.write(f'Medication already exists: {med.medication_name}')

        self.stdout.write(self.style.SUCCESS('Successfully populated medications'))
