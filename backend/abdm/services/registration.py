from django.utils import timezone
from abdm.models import ABHAProfile, ABDMSession
from abdm.services.eka_client import EKAClient
import hashlib
import logging
import re
from datetime import timedelta

logger = logging.getLogger(__name__)

class ABHARegistrationService:
    """Handle ABHA registration with proper validation"""
    
    def __init__(self):
        self.client = EKAClient()
    
    def _validate_mobile(self, mobile: str) -> str:
        """
        Validate and format mobile number for ABDM
        
        Rules:
        - Must be Indian mobile: starts with +91
        - Must be 10 digits after country code
        - Total 13 characters (+91XXXXXXXXXX)
        
        Args:
            mobile: Raw mobile number (can be with/without +91)
        
        Returns:
            Formatted mobile number: +91XXXXXXXXXX
        
        Raises:
            ValueError: If mobile number is invalid
        """
        # Remove all spaces and special characters except +
        mobile = re.sub(r'[^\d+]', '', mobile)
        
        # If doesn't start with +91, add it
        if not mobile.startswith('+91'):
            if mobile.startswith('91'):
                mobile = '+' + mobile
            elif mobile.startswith('+'):
                mobile = '+91' + mobile[1:]
            else:
                mobile = '+91' + mobile
        
        # Validate format
        if not re.match(r'^\+91\d{10}$', mobile):
            raise ValueError(
                f"Invalid mobile number: {mobile}. "
                "Must be 10 digits after +91 (e.g., +919876543210)"
            )
        
        return mobile
    
    def initiate_registration(self, mobile: str) -> dict:
        """
        Step 1: Send OTP to mobile for registration
        
        Args:
            mobile: Mobile number (will be auto-formatted)
        
        Returns:
            {
                'txn_id': 'xxx',
                'message': 'OTP sent to +919876543210'
            }
        """
        try:
            # Validate and format mobile
            formatted_mobile = self._validate_mobile(mobile)
            logger.info(f"📱 Initiating registration for: {formatted_mobile}")
            
            # Call EKA API
            response = self.client.initiate_mobile_registration(formatted_mobile)
            txn_id = response.get('txn_id')
            
            if not txn_id:
                raise Exception("No transaction ID received from ABDM")
            
            # Create session
            expires_at = timezone.now() + timedelta(minutes=5)
            ABDMSession.objects.create(
                txn_id=txn_id,
                mobile=formatted_mobile,
                session_type='registration',
                expires_at=expires_at
            )
            
            logger.info(f"✅ OTP sent successfully. TxnID: {txn_id}")
            
            return {
                'txn_id': txn_id,
                'mobile': formatted_mobile,
                'message': f'OTP sent to {formatted_mobile}',
                'expires_in': 300  # 5 minutes
            }
            
        except ValueError as e:
            logger.error(f"❌ Validation error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"❌ Registration initiation failed: {str(e)}")
            raise
    
    def verify_registration_otp(self, txn_id: str, otp: str) -> dict:
        """
        Step 2: Verify OTP
        """
        logger.info(f"🔐 Verifying OTP for txn: {txn_id}")
        
        try:
            # Verify session exists
            session = ABDMSession.objects.get(
                txn_id=txn_id, 
                session_type='registration'
            )
            
            if session.expires_at < timezone.now():
                raise Exception("OTP expired. Please request a new one.")
            
            # Call EKA API
            response = self.client.verify_mobile_otp(txn_id, otp)
            
            # Mark session as verified
            session.is_verified = True
            session.save()
            
            logger.info(f"✅ OTP verified successfully")
            
            return {
                'txn_id': txn_id,
                'existing_abha_addresses': response.get('abha_addresses', []),
                'skip_state': response.get('skip_state', 'abha_create'),
                'message': 'OTP verified successfully'
            }
            
        except ABDMSession.DoesNotExist:
            logger.error(f"❌ Invalid session: {txn_id}")
            raise Exception("Invalid or expired session. Please start registration again.")
        except Exception as e:
            logger.error(f"❌ OTP verification failed: {str(e)}")
            raise
    
    def create_abha_address(
        self, 
        txn_id: str, 
        abha_address: str, 
        patient
    ) -> ABHAProfile:
        """
        Step 3: Create ABHA address
        """
        logger.info(f"🆕 Creating ABHA: {abha_address}@abdm")
        
        try:
            # Verify session
            session = ABDMSession.objects.get(
                txn_id=txn_id,
                session_type='registration',
                is_verified=True
            )
            
            if session.expires_at < timezone.now():
                raise Exception("Session expired")
            
            # Prepare profile data
            user = patient.user
            profile_data = {
                'first_name': user.first_name,
                'last_name': user.last_name or '',
                'gender': patient.gender,
                'year_of_birth': user.date_of_birth.year,
                'month_of_birth': user.date_of_birth.month,
                'day_of_birth': user.date_of_birth.day,
                'pincode': '560001',  # TODO: Get from patient
            }
            
            # Call EKA API
            response = self.client.create_abha_address(
                txn_id, 
                abha_address, 
                profile_data
            )
            
            # Extract profile data from response
            profile = response.get('profile', {})
            eka_ids = response.get('eka', {})
            
            # Create ABHA profile
            abha_profile = ABHAProfile.objects.create(
                patient=patient,
                abha_address=f"{abha_address}@abdm",
                abha_number=profile.get('abha_number') or None,
                full_name=f"{profile.get('first_name', '')} {profile.get('last_name', '')}".strip(),
                date_of_birth=user.date_of_birth,
                gender=profile.get('gender'),
                mobile=session.mobile,
                abdm_access_token=response.get('token'),
                token_expires_at=timezone.now() + timedelta(seconds=1800),
                refresh_token=response.get('refresh_token')
            )
            
            # Store OID if provided
            if eka_ids.get('oid'):
                patient.oid = eka_ids['oid']
                patient.save()
            
            logger.info(f"✅ ABHA created: {abha_profile.abha_address}")
            
            # Clean up session
            session.delete()
            
            return abha_profile
            
        except ABDMSession.DoesNotExist:
            raise Exception("Invalid or expired session")
        except Exception as e:
            logger.error(f"❌ ABHA creation failed: {str(e)}")
            raise
    
    # ==================== LOGIN METHODS ====================
    
    def initiate_login(self, mobile: str) -> dict:
        """
        Step 1: Initiate ABHA login
        """
        try:
            formatted_mobile = self._validate_mobile(mobile)
            logger.info(f"📱 Initiating login for: {formatted_mobile}")
            
            response = self.client.initiate_login(formatted_mobile)
            txn_id = response.get('txn_id')
            
            if not txn_id:
                raise Exception("No transaction ID received")
            
            # Create session
            expires_at = timezone.now() + timedelta(minutes=5)
            ABDMSession.objects.create(
                txn_id=txn_id,
                mobile=formatted_mobile,
                session_type='login',
                expires_at=expires_at
            )
            
            logger.info(f"✅ Login OTP sent. TxnID: {txn_id}")
            
            return {
                'txn_id': txn_id,
                'mobile': formatted_mobile,
                'message': f'OTP sent to {formatted_mobile}'
            }
            
        except Exception as e:
            logger.error(f"❌ Login initiation failed: {str(e)}")
            raise
    
    def verify_login_otp(self, txn_id: str, otp: str, patient=None):
        """
        Step 2: Verify login OTP
        Returns full response including skip_state and abha_profiles
        """
        try:
            session = ABDMSession.objects.get(
                txn_id=txn_id,
                session_type='login'
            )
            
            # Verify OTP with Eka.Care
            response = self.client.verify_login_otp(txn_id, otp)
            
            logger.info(f"✅ Login OTP verified for {session.mobile}")
            logger.debug(f"Response: {response}")
            
            # Extract data from response
            skip_state = response.get('skip_state')
            profile = response.get('profile', {})
            abha_profiles = response.get('abha_profiles', [])

            # Find patient by mobile if not provided
            if not patient:
                from patients.models import PatientProfile
                try:
                    mobile = session.mobile
                    patient = PatientProfile.objects.filter(user__phone_number=mobile).first()
                    # Try without +91 if not found
                    if not patient and mobile.startswith('+91'):
                        raw_mobile = mobile[3:]
                        patient = PatientProfile.objects.filter(user__phone_number=raw_mobile).first()
                except Exception:
                    logger.warning(f"Could not find patient for mobile {session.mobile}")
            
            tokens = None
            if skip_state == 'abha_end' and patient:
                # Login is considered complete here (e.g. valid session exists or auto-selected)
                # Ensure we have a user to generate tokens for
                from rest_framework_simplejwt.tokens import RefreshToken
                refresh = RefreshToken.for_user(patient.user)
                tokens = {
                    'access': str(refresh.access_token),
                    'refresh': str(refresh),
                }
                
                # Update/Create profile if we have profile data
                if profile:
                    abha_profile, created = ABHAProfile.objects.update_or_create(
                        patient=patient,
                        abha_address=profile.get('abha_address'),
                        defaults={
                            'abha_number': profile.get('abha_number') or None,
                            'full_name': f"{profile.get('first_name', '')} {profile.get('last_name', '')}".strip(),
                            'gender': profile.get('gender'),
                            'mobile': session.mobile,
                            'abdm_access_token': response.get('token'),
                            'token_expires_at': timezone.now() + timedelta(seconds=1800),
                            'refresh_token': response.get('refresh_token')
                        }
                    )
            
            # Return full response for frontend to handle

            return {
                'txn_id': response.get('txn_id', txn_id),
                'skip_state': skip_state,
                'abha_profiles': abha_profiles,
                'profile': profile,
                'tokens': tokens,
                'message': 'OTP verified successfully'
            }

            
        except ABDMSession.DoesNotExist:
            raise Exception("Invalid or expired session")
        except Exception as e:
            logger.error(f"❌ Login OTP verification failed: {str(e)}")
            raise
    
    def complete_login(self, txn_id: str, abha_address: str, patient=None):
        """
        Step 3: Complete login by selecting ABHA address
        Only needed when skip_state is 'abha_select'
        """
        try:
            session = ABDMSession.objects.get(
                txn_id=txn_id,
                session_type='login'
            )
            
            # Call the login endpoint
            response = self.client.login_abha_address(txn_id, abha_address)
            
            logger.info(f"✅ Login completed for {abha_address}")
            
            # Extract profile data
            profile = response.get('profile', {})

            # Find patient by mobile if not provided
            if not patient:
                from patients.models import PatientProfile
                try:
                    mobile = session.mobile
                    patient = PatientProfile.objects.filter(user__phone_number=mobile).first()
                     # Try without +91 if not found
                    if not patient and mobile.startswith('+91'):
                        raw_mobile = mobile[3:]
                        patient = PatientProfile.objects.filter(user__phone_number=raw_mobile).first()
                except Exception:
                    pass
            
            # If patient is provided, link or update ABHA profile
            if patient:
                abha_profile, created = ABHAProfile.objects.update_or_create(
                    patient=patient,
                    abha_address=abha_address,

                    defaults={
                        'abha_number': profile.get('abha_number') or None,
                        'full_name': f"{profile.get('first_name', '')} {profile.get('last_name', '')}".strip(),
                        'gender': profile.get('gender'),
                        'mobile': session.mobile,
                        'abdm_access_token': response.get('token'),
                        'token_expires_at': timezone.now() + timedelta(seconds=1800),
                        'refresh_token': response.get('refresh_token')
                    }
                )
                logger.info(f"{'Created' if created else 'Updated'} ABHA profile: {abha_address}")
            
            # Clean up session
            session.delete()
            
            # Generate JWT tokens for the app session
            tokens = None
            if patient:
                from rest_framework_simplejwt.tokens import RefreshToken
                refresh = RefreshToken.for_user(patient.user)
                tokens = {
                    'access': str(refresh.access_token),
                    'refresh': str(refresh),
                }
            
            return {
                'profile': profile,
                'tokens': tokens,
                'message': 'Login successful'
            }

            
        except ABDMSession.DoesNotExist:
            raise Exception("Invalid or expired session")
        except Exception as e:
            logger.error(f"❌ Login completion failed: {str(e)}")
            raise

