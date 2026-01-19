import os
import sys
import django
from datetime import datetime, timedelta
from django.utils import timezone

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "carepal.settings")
django.setup()

from django.contrib.auth import get_user_model
from patients.models import PatientProfile
from vitals.models import VitalType, VitalReading
from medications.models import Medication, MedicationSchedule, MedicationAdherence
import random

User = get_user_model()

def populate_data():
    print("=" * 60)
    print("POPULATING COMPREHENSIVE TEST DATA")
    print("=" * 60)
    
    # Get or create user
    username = "ameena"
    try:
        user = User.objects.get(username=username)
        print(f"✅ Found user: {username}")
    except User.DoesNotExist:
        print(f"❌ User {username} not found")
        return
    
    # Get patient profile
    try:
        profile = PatientProfile.objects.get(user=user)
        print(f"✅ Found patient profile for {username}")
    except PatientProfile.DoesNotExist:
        print(f"❌ Patient profile not found for {username}")
        return
    
    print(f"\n📊 Patient ID: {profile.id}")
    print(f"📊 Patient Name: {profile.user.get_full_name()}")
    
    # Create Vital Types
    print("\n" + "=" * 60)
    print("CREATING VITAL TYPES")
    print("=" * 60)
    
    vital_types_data = [
        {
            'code': 'BP',
            'name': 'Blood Pressure',
            'category': 'CARDIOVASCULAR',
            'unit': 'mmHg',
            'requires_multiple_values': True,
            'normal_range': {'systolic_min': 90, 'systolic_max': 120, 'diastolic_min': 60, 'diastolic_max': 80}
        },
        {
            'code': 'HR',
            'name': 'Heart Rate',
            'category': 'CARDIOVASCULAR',
            'unit': 'bpm',
            'is_continuous': True,
            'normal_range': {'min': 60, 'max': 100}
        },
        {
            'code': 'SPO2',
            'name': 'Oxygen Saturation',
            'category': 'RESPIRATORY',
            'unit': 'percent',
            'normal_range': {'min': 95, 'max': 100}
        },
        {
            'code': 'TEMP',
            'name': 'Body Temperature',
            'category': 'BODY',
            'unit': 'fahrenheit',
            'normal_range': {'min': 97.0, 'max': 99.0}
        },
    ]
    
    vital_types = {}
    for vt_data in vital_types_data:
        vt, created = VitalType.objects.get_or_create(
            code=vt_data['code'],
            defaults=vt_data
        )
        vital_types[vt.code] = vt
        print(f"{'✅ Created' if created else '✅ Found'} VitalType: {vt.code} - {vt.name}")
    
    # Create Vital Readings for the past 7 days
    print("\n" + "=" * 60)
    print("CREATING VITAL READINGS (Last 7 days)")
    print("=" * 60)
    
    # Delete old readings for this patient
    old_count = VitalReading.objects.filter(patient=profile).count()
    VitalReading.objects.filter(patient=profile).delete()
    print(f"🗑️  Deleted {old_count} old vital readings")
    
    now = timezone.now()
    readings_created = 0
    
    for days_ago in range(7):
        date = now - timedelta(days=days_ago)
        
        # BP readings (2 per day)
        for hour in [8, 20]:  # Morning and evening
            reading_time = date.replace(hour=hour, minute=random.randint(0, 59))
            systolic = random.randint(110, 130)
            diastolic = random.randint(70, 85)
            
            VitalReading.objects.create(
                patient=profile,
                vital_type=vital_types['BP'],
                values={'systolic': systolic, 'diastolic': diastolic},
                unit='mmHg',
                measured_at=reading_time
            )
            readings_created += 1
        
        # HR readings (3 per day)
        for hour in [8, 14, 20]:
            reading_time = date.replace(hour=hour, minute=random.randint(0, 59))
            hr_value = random.randint(65, 85)
            
            VitalReading.objects.create(
                patient=profile,
                vital_type=vital_types['HR'],
                value=hr_value,
                unit='bpm',
                measured_at=reading_time
            )
            readings_created += 1
        
        # SpO2 readings (2 per day)
        for hour in [9, 21]:
            reading_time = date.replace(hour=hour, minute=random.randint(0, 59))
            spo2_value = random.randint(96, 99)
            
            VitalReading.objects.create(
                patient=profile,
                vital_type=vital_types['SPO2'],
                value=spo2_value,
                unit='percent',
                measured_at=reading_time
            )
            readings_created += 1
        
        # Temperature readings (1 per day)
        reading_time = date.replace(hour=10, minute=random.randint(0, 59))
        temp_value = round(random.uniform(97.5, 98.6), 1)
        
        VitalReading.objects.create(
            patient=profile,
            vital_type=vital_types['TEMP'],
            value=temp_value,
            unit='fahrenheit',
            measured_at=reading_time
        )
        readings_created += 1
    
    print(f"✅ Created {readings_created} vital readings")
    
    # Create Medications
    print("\n" + "=" * 60)
    print("CREATING MEDICATIONS")
    print("=" * 60)
    
    # Delete old medications
    old_med_count = Medication.objects.filter(patient=profile).count()
    Medication.objects.filter(patient=profile).delete()
    print(f"🗑️  Deleted {old_med_count} old medications")
    
    medications_data = [
        {
            'medication_name': 'Lisinopril',
            'dosage': '10mg',
            'form': 'TABLET',
            'route': 'ORAL',
            'frequency': 'ONCE_DAILY',
            'times_per_day': 1,
            'is_critical': True,
            'instructions': 'Take once daily in the morning',
        },
        {
            'medication_name': 'Metformin',
            'dosage': '500mg',
            'form': 'TABLET',
            'route': 'ORAL',
            'frequency': 'TWICE_DAILY',
            'times_per_day': 2,
            'is_critical': True,
            'instructions': 'Take with meals',
        },
        {
            'medication_name': 'Vitamin D',
            'dosage': '1000 IU',
            'form': 'CAPSULE',
            'route': 'ORAL',
            'frequency': 'ONCE_DAILY',
            'times_per_day': 1,
            'is_critical': False,
            'instructions': 'Take with food',
        },
    ]
    
    medications = []
    for med_data in medications_data:
        med = Medication.objects.create(
            patient=profile,
            **med_data,
            start_date=now.date() - timedelta(days=30),
            status='ACTIVE',
            created_by=user
        )
        medications.append(med)
        print(f"✅ Created Medication: {med.medication_name} {med.dosage}")
        
        # Create schedules
        if med.frequency in ['ONCE_DAILY', 'TWICE_DAILY', 'THREE_TIMES_DAILY']:
            if med.times_per_day == 1:
                times = ['08:00:00']
            elif med.times_per_day == 2:
                times = ['08:00:00', '20:00:00']
            elif med.times_per_day == 3:
                times = ['08:00:00', '14:00:00', '20:00:00']
            else:
                times = ['08:00:00']
            
            for time_str in times:
                schedule = MedicationSchedule.objects.create(
                    medication=med,
                    time_of_day=time_str,
                    is_active=True
                )
                print(f"  📅 Created schedule at {time_str}")
                
                # Skip adherence records for now - focus on vitals
                # # Create adherence records for past 7 days
                # for days_ago in range(7):
                #     adherence_date = now.date() - timedelta(days=days_ago)
                #     scheduled_time = datetime.combine(adherence_date, datetime.strptime(time_str, '%H:%M:%S').time())
                #     scheduled_datetime = timezone.make_aware(scheduled_time)
                #     
                #     # 80% adherence rate
                #     status = 'TAKEN' if random.random() < 0.8 else 'MISSED'
                #     
                #     MedicationAdherence.objects.create(
                #         medication=med,
                #         schedule=schedule,
                #         scheduled_date=adherence_date,
                #         scheduled_datetime=scheduled_datetime,
                #         status=status,
                #         taken_at=scheduled_datetime if status == 'TAKEN' else None
                #     )
    
    adherence_count = MedicationAdherence.objects.filter(medication__patient=profile).count()
    print(f"✅ Created {adherence_count} medication adherence records")
    
    # Verify data
    print("\n" + "=" * 60)
    print("DATA VERIFICATION")
    print("=" * 60)
    
    total_vitals = VitalReading.objects.filter(patient=profile).count()
    print(f"📊 Total Vital Readings: {total_vitals}")
    
    for vt_code, vt in vital_types.items():
        count = VitalReading.objects.filter(patient=profile, vital_type=vt).count()
        print(f"   - {vt.name} ({vt_code}): {count} readings")
    
    total_meds = Medication.objects.filter(patient=profile, status='ACTIVE').count()
    print(f"📊 Total Active Medications: {total_meds}")
    
    total_adherence = MedicationAdherence.objects.filter(medication__patient=profile).count()
    taken = MedicationAdherence.objects.filter(medication__patient=profile, status='TAKEN').count()
    adherence_rate = (taken / total_adherence * 100) if total_adherence > 0 else 0
    print(f"📊 Medication Adherence: {taken}/{total_adherence} ({adherence_rate:.1f}%)")
    
    print("\n" + "=" * 60)
    print("✅ DATA POPULATION COMPLETE!")
    print("=" * 60)

if __name__ == "__main__":
    populate_data()
