import os
import django
import random
from datetime import datetime, timedelta
from decimal import Decimal

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'carepal.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.utils import timezone
from patients.models import PatientProfile, EmergencyContact
from vitals.models import VitalType, VitalReading, DataSource
from medications.models import Medication, MedicationAdherence
from medications.schedule_utils import default_dose_times_for_frequency
from family.models import FamilyMember
from alerts.models import Alert, AlertType

User = get_user_model()

class TestDataPopulator:
    def __init__(self):
        self.users = []
        self.patient_profiles = []
        self.vital_types = {}
        self.medications = []
        self.alert_types = {}
        self.data_sources = {}
        
    def run(self):
        print("🚀 Starting test data population (Corrected Schema)...\n")
        
        self.create_users()
        self.create_patients_and_contacts()
        self.create_data_sources()
        self.create_vital_types()
        self.create_vital_readings()
        self.create_medications()
        self.create_medication_schedules()
        self.create_medication_adherence()
        self.create_family_members()
        self.create_alert_types()
        self.create_alerts()
        
        print("\n✅ Test data population complete!")
        self.print_summary()
    
    def create_users(self):
        print("👤 Creating test users...")
        users_data = [
            {
                'username': 'elderly_patient1', 'email': 'patient1@carepal.com', 
                'password': 'Test@1234', 'first_name': 'Robert', 'last_name': 'Johnson',
                'phone_number': '+15550000001'
            },
            {
                'username': 'elderly_patient2', 'email': 'patient2@carepal.com', 
                'password': 'Test@1234', 'first_name': 'Mary', 'last_name': 'Williams',
                'phone_number': '+15550000002'
            },
            {
                'username': 'test_patient', 'email': 'test@carepal.com', 
                'password': 'Test@1234', 'first_name': 'John', 'last_name': 'Doe',
                'phone_number': '+15550000003'
            },
        ]
        
        for user_data in users_data:
            user, created = User.objects.get_or_create(
                username=user_data['username'],
                defaults={
                    'email': user_data['email'],
                    'first_name': user_data['first_name'],
                    'last_name': user_data['last_name'],
                    'phone_number': user_data['phone_number'],
                    'is_active': True,
                }
            )
            if created:
                user.set_password(user_data['password'])
                user.save()
            self.users.append(user)
            print(f"   ✓ User: {user.username}")
    
    def create_patients_and_contacts(self):
        print("\n🏥 Creating patient profiles & emergency contacts...")
        
        patients_data = [
            {
                'gender': 'M', 'blood_group': 'O+', 'height_cm': 175.0, 'weight_kg': 80.5,
                'address_line1': '123 Oak Street', 'city': 'Springfield', 'state': 'IL', 'pincode': '62701',
                'medical_notes': 'Hypertension, Type 2 Diabetes',
                'contact': {'name': 'Sarah Johnson', 'relation': 'CHILD', 'phone': '+1-555-0101'}
            },
            {
                'gender': 'F', 'blood_group': 'A+', 'height_cm': 162.0, 'weight_kg': 68.0,
                'address_line1': '456 Maple Avenue', 'city': 'Chicago', 'state': 'IL', 'pincode': '60601',
                'medical_notes': 'Heart Disease, Arthritis',
                'contact': {'name': 'James Williams', 'relation': 'CHILD', 'phone': '+1-555-0102'}
            },
            {
                'gender': 'M', 'blood_group': 'B+', 'height_cm': 180.0, 'weight_kg': 85.0,
                'address_line1': '789 Pine Road', 'city': 'Boston', 'state': 'MA', 'pincode': '02101',
                'medical_notes': 'Asthma, High Cholesterol',
                'contact': {'name': 'Jane Doe', 'relation': 'SPOUSE', 'phone': '+1-555-0103'}
            },
        ]
        
        for i, user in enumerate(self.users):
            data = patients_data[i]
            contact_data = data.pop('contact')
            
            profile, created = PatientProfile.objects.get_or_create(
                user=user,
                defaults=data
            )
            self.patient_profiles.append(profile)
            
            # Create Emergency Contact
            EmergencyContact.objects.get_or_create(
                patient=profile,
                phone_number=contact_data['phone'],
                defaults={
                    'name': contact_data['name'],
                    'relationship': contact_data['relation'],
                    'is_primary': True
                }
            )
            print(f"   ✓ Profile & Contact: {user.get_full_name()}")

    def create_data_sources(self):
        print("\n📱 Creating data sources...")
        for profile in self.patient_profiles:
            ds, _ = DataSource.objects.get_or_create(
                patient=profile,
                device_identifier=f"DEV-{profile.user.username}",
                defaults={
                    'source_type': 'CAREPAL_DEVICE',
                    'device_type': 'SMARTWATCH',
                    'device_name': 'CarePal Watch',
                    'is_active': True
                }
            )
            self.data_sources[profile.id] = ds

    def create_vital_types(self):
        print("\n📊 Creating vital types...")
        types = [
            {'code': 'BP', 'name': 'Blood Pressure', 'unit': 'mmHg', 'category': 'CARDIOVASCULAR', 'requires_multiple_values': True, 'normal_range': {'systolic_min': 90, 'systolic_max': 120, 'diastolic_min': 60, 'diastolic_max': 80}},
            {'code': 'HR', 'name': 'Heart Rate', 'unit': 'bpm', 'category': 'CARDIOVASCULAR', 'normal_range': {'min': 60, 'max': 100}},
            {'code': 'SPO2', 'name': 'Oxygen Saturation', 'unit': '%', 'category': 'RESPIRATORY', 'normal_range': {'min': 95, 'max': 100}},
            {'code': 'TEMP', 'name': 'Body Temperature', 'unit': '°F', 'category': 'BODY', 'normal_range': {'min': 97.0, 'max': 99.0}},
            {'code': 'GLUCOSE', 'name': 'Blood Glucose', 'unit': 'mg/dl', 'category': 'METABOLIC', 'normal_range': {'min': 70, 'max': 140}},
            {'code': 'WEIGHT', 'name': 'Body Weight', 'unit': 'kg', 'category': 'BODY', 'normal_range': {'min': 50, 'max': 100}},
        ]
        
        for t in types:
            vt, _ = VitalType.objects.get_or_create(code=t['code'], defaults=t)
            self.vital_types[t['code']] = vt
            print(f"   ✓ Vital Type: {vt.name}")

    def create_vital_readings(self):
        print("\n💓 Creating vital readings...")
        for profile in self.patient_profiles:
            source = self.data_sources[profile.id]
            
            # Helper to create reading
            def add_reading(code, value, values=None):
                VitalReading.objects.create(
                    patient=profile,
                    vital_type=self.vital_types[code],
                    data_source=source,
                    value=value,
                    values=values or {},
                    unit=self.vital_types[code].unit,
                    measured_at=timezone.now() - timedelta(days=random.randint(0, 30), hours=random.randint(0, 23))
                )

            # Generate random data
            for _ in range(50):
                # BP
                sys = random.randint(110, 140)
                dia = random.randint(70, 90)
                add_reading('BP', None, {'systolic': sys, 'diastolic': dia})
                
                # HR
                add_reading('HR', random.randint(60, 100))
                
                # SpO2
                add_reading('SPO2', random.randint(95, 100))
                
                # Temp
                add_reading('TEMP', round(random.uniform(97.0, 99.5), 1))
            
            print(f"   ✓ Readings for {profile.user.username}")

    def create_medications(self):
        print("\n💊 Creating medications...")
        med_data = [
            {'medication_name': 'Lisinopril', 'dosage': '10mg', 'frequency': 'ONCE_DAILY', 'form': 'TABLET', 'route': 'ORAL', 'instructions': 'Morning'},
            {'medication_name': 'Metformin', 'dosage': '500mg', 'frequency': 'TWICE_DAILY', 'form': 'TABLET', 'route': 'ORAL', 'instructions': 'With meals'},
        ]
        
        for profile in self.patient_profiles:
            for m in med_data:
                med = Medication.objects.create(
                    patient=profile,
                    start_date=timezone.now().date(),
                    status='ACTIVE',
                    prescribed_by='Dr. Smith',
                    **m
                )
                self.medications.append(med)
            print(f"   ✓ Meds for {profile.user.username}")

    def create_medication_schedules(self):
        print("\n📅 Setting medication dose_times...")
        for med in self.medications:
            if not med.dose_times:
                med.dose_times = default_dose_times_for_frequency(med.frequency)
                med.save(update_fields=['dose_times'])
        print("   ✓ dose_times set")

    def create_medication_adherence(self):
        print("\n✅ Creating adherence records...")
        # Simplification: Create a few adherence records for "today"
        now = timezone.now()
        for med in self.medications:
            MedicationAdherence.objects.create(
                medication=med,
                scheduled_date=now.date(),
                scheduled_time=now.time(),
                scheduled_datetime=now,
                status='TAKEN',
                actual_datetime=now
            )
        print("   ✓ Adherence records created")

    def create_family_members(self):
        # Already created users for family in previous step? No, need new users.
        # For simplicity, skip creating new Users for family in this basic script unless critical.
        # But FamilyMember needs a User.
        pass

    def create_alert_types(self):
        print("\n🚨 Creating alert types...")
        types = [
            {'code': 'VITAL_HIGH', 'name': 'High Vital', 'category': 'VITAL_ANOMALY', 'default_severity': 'WARNING', 'message_template': '{vital} is high: {value}'},
            {'code': 'MED_MISSED', 'name': 'Missed Medication', 'category': 'MEDICATION', 'default_severity': 'WARNING', 'message_template': 'Missed {medication} at {time}'},
        ]
        for t in types:
            at, _ = AlertType.objects.get_or_create(code=t['code'], defaults=t)
            self.alert_types[t['code']] = at

    def create_alerts(self):
        print("\n🔔 Creating alerts...")
        for profile in self.patient_profiles:
            Alert.objects.create(
                alert_type=self.alert_types['VITAL_HIGH'],
                patient=profile,
                severity='WARNING',
                title='High Blood Pressure',
                message='BP is 140/90',
                status='PENDING'
            )
        print("   ✓ Alerts created")

    def print_summary(self):
        print("\n📊 Summary:")
        print(f"Users: {User.objects.count()}")
        print(f"Patients: {PatientProfile.objects.count()}")
        print(f"Vitals: {VitalReading.objects.count()}")
        print(f"Meds: {Medication.objects.count()}")

if __name__ == '__main__':
    TestDataPopulator().run()
