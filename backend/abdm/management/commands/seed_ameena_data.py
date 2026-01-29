from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from patients.models import PatientProfile
from vitals.models import VitalReading, VitalType
from datetime import datetime, timedelta
import random
from django.utils import timezone

User = get_user_model()

class Command(BaseCommand):
    help = 'Seeds random data for user ameena'

    def handle(self, *args, **kwargs):
        username = 'ameena'
        password = 'passme123'
        
        # 1. Get or Create User
        user, created = User.objects.get_or_create(username=username)
        if created:
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(f"Created User: {username}"))
        else:
            self.stdout.write(f"User {username} already exists")

        # 2. Get or Create Patient Profile
        profile, created = PatientProfile.objects.get_or_create(
            user=user,
            defaults={
                'first_name': 'Ameena',
                'last_name': 'Muneer',
                'date_of_birth': '1995-01-01',
                'gender': 'FEMALE',
                'mobile_number': '9947343327' # Using the number from previous logs
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created PatientProfile for {username}"))

        # 3. Create Vital Types if missing
        bp_type, _ = VitalType.objects.get_or_create(
            code='BP', 
            defaults={'name': 'Blood Pressure', 'unit': 'mmHg', 'category': 'CARDIOVASCULAR', 'requires_multiple_values': True}
        )
        hr_type, _ = VitalType.objects.get_or_create(
            code='HR', 
            defaults={'name': 'Heart Rate', 'unit': 'bpm', 'category': 'CARDIOVASCULAR'}
        )
        spo2_type, _ = VitalType.objects.get_or_create(
            code='SPO2', 
            defaults={'name': 'SpO2', 'unit': 'percent', 'category': 'RESPIRATORY'}
        )
        temp_type, _ = VitalType.objects.get_or_create(
            code='TEMP', 
            defaults={'name': 'Temperature', 'unit': 'celsius', 'category': 'BODY'}
        )

        # 4. Generate Random Readings (Past 30 Days)
        end_date = timezone.now()
        readings_created = 0
        
        for i in range(20):
            # Random time in last 30 days
            delta = timedelta(days=random.randint(0, 30), hours=random.randint(0, 23))
            timestamp = end_date - delta
            
            # BP
            systolic = random.randint(110, 140)
            diastolic = random.randint(70, 90)
            VitalReading.objects.create(
                patient=profile,
                vital_type=bp_type,
                values={'systolic': systolic, 'diastolic': diastolic},
                unit='mmHg',
                measured_at=timestamp
            )
            
            # HR
            hr = random.randint(60, 100)
            VitalReading.objects.create(
                patient=profile,
                vital_type=hr_type,
                value=hr,
                unit='bpm',
                measured_at=timestamp
            )
            
            # SpO2
            spo2 = random.randint(95, 100)
            VitalReading.objects.create(
                patient=profile,
                vital_type=spo2_type,
                value=spo2,
                unit='%',
                measured_at=timestamp
            )
            
            readings_created += 3
            
        self.stdout.write(self.style.SUCCESS(f"✅ Successfully seeded {readings_created} vital readings for {username}"))
