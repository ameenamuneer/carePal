import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'carepal.settings')
django.setup()

from django.contrib.auth import get_user_model
User = get_user_model()

username = "ameena"
password = "passme123"
email = "ameena@example.com"
import random
phone = f"555{random.randint(1000000, 9999999)}"

if not User.objects.filter(username=username).exists():
    print(f"Creating user {username}...")
    try:
        user = User.objects.create_user(username=username, email=email, password=password, phone_number=phone)
        user.first_name = "Ameena"
        user.last_name = "User"
        user.save()
        print(f"User {username} created successfully.")
    except Exception as e:
        print(f"Error creating user: {e}")
else:
    print(f"User {username} already exists. Updating password...")
    u = User.objects.get(username=username)
    u.set_password(password)
    u.save()
    print(f"Password updated for {username}.")

# Update User details
user = User.objects.get(username=username)
user.phone_number = '5551234567'
user.date_of_birth = '1990-01-01'
user.save()

# Create Patient Profile
try:
    from patients.models import PatientProfile, EmergencyContact
    
    profile, created = PatientProfile.objects.get_or_create(
        user=user,
        defaults={
            'gender': 'F',
            'blood_group': 'O+',
            'address_line1': '123 Care Lane',
            'city': 'Cyber City',
            'state': 'Tech State',
            'pincode': '12345',
            'country': 'India',
        }
    )
    if created:
        print(f"PatientProfile created for {username}.")
    else:
        print(f"PatientProfile already exists for {username}.")

    # Create Emergency Contact
    EmergencyContact.objects.get_or_create(
        patient=profile,
        phone_number='555-0100',
        defaults={
            'name': 'Emergency Contact',
            'relationship': 'FRIEND',
            'is_primary': True
        }
    )

    # Create dummy Vitals for dashboard
    from vitals.models import VitalType, VitalReading
    from django.utils import timezone
    import random
    
    # Create VitalTypes
    bp_type, _ = VitalType.objects.get_or_create(
        code='BP',
        defaults={
            'name': 'Blood Pressure',
            'category': 'CARDIOVASCULAR',
            'unit': 'mmHg',
            'requires_multiple_values': True
        }
    )
    
    hr_type, _ = VitalType.objects.get_or_create(
        code='HR',
        defaults={
            'name': 'Heart Rate',
            'category': 'CARDIOVASCULAR',
            'unit': 'bpm',
            'is_continuous': True
        }
    )

    # Create Readings
    # BP Reading
    VitalReading.objects.create(
        patient=profile,
        vital_type=bp_type,
        values={'systolic': 120, 'diastolic': 80},
        unit='mmHg',
        measured_at=timezone.now()
    )
    
    # HR Reading
    VitalReading.objects.create(
        patient=profile,
        vital_type=hr_type,
        value=75,
        unit='bpm',
        measured_at=timezone.now()
    )
    
    # Add a few more HR readings for history
    for i in range(5):
        VitalReading.objects.create(
            patient=profile,
            vital_type=hr_type,
            value=70 + random.randint(-5, 5),
            unit='bpm',
            measured_at=timezone.now() - timezone.timedelta(hours=i*2)
        )
        
    print("Dummy vitals created successfully.")

except Exception as e:
    import traceback
    traceback.print_exc()
    print(f"Error checking/creating profile: {e}")
