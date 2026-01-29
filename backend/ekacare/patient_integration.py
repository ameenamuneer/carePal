from django.utils import timezone
from django.db import transaction
from .authentication import EkaCareAuth, EkaCareAPIException
import logging

logger = logging.getLogger(__name__)


class EkaCarePatientIntegration:
    """
    Complete patient integration with Eka.Care
    Handles patient creation, ABHA registration, and ID linking
    """
    
    @staticmethod
    def create_patient_in_ekacare(patient_profile):
        """
        Create patient in Eka.Care Patient Directory
        
        Args:
            patient_profile: CarePAL PatientProfile instance
        
        Returns:
            dict: Eka.Care patient data with patient_id
        """
        # Prepare patient data for Eka.Care
        patient_data = {
            'first_name': patient_profile.user.first_name,
            'last_name': patient_profile.user.last_name,
            'mobile': patient_profile.phone,
            'dob': patient_profile.date_of_birth.strftime('%Y-%m-%d') 
                   if patient_profile.date_of_birth else None,
            'gender': patient_profile.gender,
            
            # Send our CarePAL ID as partner_patient_id
            'partner_patient_id': patient_profile.partner_patient_id,
            
            # Include ABHA if available
            'abha': patient_profile.abha_number if patient_profile.has_abha else None,
            
            # Optional metadata
            'metadata': {
                'carepal_patient_id': patient_profile.id,
                'created_at': timezone.now().isoformat()
            }
        }
        
        # Remove None values
        patient_data = {k: v for k, v in patient_data.items() if v is not None}
        
        # Create patient in Eka.Care
        try:
            result = EkaCareAuth.make_request(
                'POST',
                '/dr/v1/patient',
                data=patient_data
            )
            
            logger.info(
                f"Created patient in Eka.Care: CarePAL ID {patient_profile.id}, "
                f"Eka ID {result.get('patient_id')}"
            )
            
            return result
            
        except EkaCareAPIException as e:
            logger.error(f"Failed to create patient in Eka.Care: {str(e)}")
            raise
    
    @staticmethod
    def search_patient_by_mobile(mobile):
        """
        Search for patient in Eka.Care by mobile number
        
        Args:
            mobile: 10-digit mobile number
        
        Returns:
            dict or None: Patient data if found
        """
        try:
            result = EkaCareAuth.make_request(
                'GET',
                '/dr/v1/business/patients/search',
                params={'mobile': mobile}
            )
            
            # Return first patient if found
            patients = result.get('patients', [])
            if patients:
                return patients[0]
            
            return None
            
        except EkaCareAPIException as e:
            logger.warning(f"Patient search failed: {str(e)}")
            return None
    
    @staticmethod
    def get_patient_details(eka_patient_id):
        """
        Get patient details from Eka.Care
        
        Args:
            eka_patient_id: Eka.Care patient_id
        
        Returns:
            dict: Patient details
        """
        try:
            result = EkaCareAuth.make_request(
                'GET',
                f'/dr/v1/patient/{eka_patient_id}'
            )
            return result
            
        except EkaCareAPIException as e:
            logger.error(f"Failed to get patient details: {str(e)}")
            raise
    
    @staticmethod
    def ensure_patient_in_ekacare(patient_profile):
        """
        Ensure patient exists in Eka.Care directory
        Creates if doesn't exist, returns existing if already created
        
        Args:
            patient_profile: CarePAL PatientProfile instance
        
        Returns:
            str: Eka.Care patient_id
        """
        # Already created?
        if patient_profile.has_eka_patient:
            logger.info(
                f"Patient {patient_profile.id} already exists in Eka.Care: "
                f"{patient_profile.eka_patient_id}"
            )
            return patient_profile.eka_patient_id
        
        # Search by mobile first (might already exist)
        existing = EkaCarePatientIntegration.search_patient_by_mobile(
            patient_profile.phone
        )
        
        if existing:
            eka_patient_id = existing.get('patient_id')
            logger.info(
                f"Found existing patient in Eka.Care by mobile: {eka_patient_id}"
            )
            
            # Link to CarePAL patient
            with transaction.atomic():
                patient_profile.eka_patient_id = eka_patient_id
                patient_profile.eka_patient_created = True
                patient_profile.eka_patient_created_at = timezone.now()
                patient_profile.save()
            
            return eka_patient_id
        
        # Create new patient
        result = EkaCarePatientIntegration.create_patient_in_ekacare(
            patient_profile
        )
        
        eka_patient_id = result.get('patient_id')
        
        # Link to CarePAL patient
        with transaction.atomic():
            patient_profile.eka_patient_id = eka_patient_id
            patient_profile.eka_patient_created = True
            patient_profile.eka_patient_created_at = timezone.now()
            patient_profile.eka_sync_metadata = {
                'eka_creation_response': result,
                'created_at': timezone.now().isoformat()
            }
            patient_profile.save()
        
        logger.info(
            f"Linked patient: CarePAL {patient_profile.id} → "
            f"Eka {eka_patient_id}"
        )
        
        return eka_patient_id
    
    @staticmethod
    def update_patient_abha(patient_profile, abha_number, abha_address):
        """
        Update patient's ABHA in both CarePAL and Eka.Care
        
        Args:
            patient_profile: CarePAL PatientProfile instance
            abha_number: ABHA number
            abha_address: ABHA address
        """
        with transaction.atomic():
            # Update in CarePAL
            patient_profile.abha_number = abha_number
            patient_profile.abha_address = abha_address
            patient_profile.is_abha_verified = True
            patient_profile.abha_created_at = timezone.now()
            patient_profile.save()
        
        # Update in Eka.Care if patient exists there
        if patient_profile.has_eka_patient:
            try:
                EkaCareAuth.make_request(
                    'PUT',
                    f'/dr/v1/patient/{patient_profile.eka_patient_id}',
                    data={'abha': abha_number}
                )
                logger.info(
                    f"Updated ABHA in Eka.Care for patient {patient_profile.id}"
                )
            except EkaCareAPIException as e:
                logger.warning(
                    f"Failed to update ABHA in Eka.Care: {str(e)}"
                )
