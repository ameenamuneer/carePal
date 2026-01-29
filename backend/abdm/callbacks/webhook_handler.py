
import logging
from dateutil.parser import parse
from django.contrib.auth import get_user_model
from abdm.models import ABDMSubscription, ABHAProfile, CareContext

logger = logging.getLogger(__name__)
User = get_user_model()

class WebhookHandler:
    
    @staticmethod
    def handle_event(event, payload):
        """
        Dispatch event to appropriate handler method
        """
        logger.info(f"⚡️ Handling Event: {event}")
        
        handler_map = {
            # PHR / User Side Events
            'abha.locker_created': WebhookHandler.handle_locker_created,
            'abha.subscription_modified': WebhookHandler.handle_subscription_modified,
            'abha.subscription_notify': WebhookHandler.handle_subscription_notify,
            
            # HIP / Provider Side Events
            'abha.care_context_discover': WebhookHandler.handle_discovery,
            'abha.care.context_discover_link_init': WebhookHandler.handle_link_init,
            'abha.context_discover_link_confirm': WebhookHandler.handle_link_confirm,
            'abha.hip_profile_share': WebhookHandler.handle_profile_share,
            'abha.hip_data_fetch': WebhookHandler.handle_data_fetch,
        }
        
        handler = handler_map.get(event)
        if handler:
            return handler(payload)
        else:
            logger.warning(f"⚠️ No handler for event: {event}")
            return None

    # ==================== PHR EVENT HANDLERS ====================

    @staticmethod
    def handle_locker_created(payload):
        sub_id = payload.get('subscription_id')
        abha_addr = payload.get('abha_address')
        
        if sub_id:
            user = None
            try:
                profile = ABHAProfile.objects.get(abha_address=abha_addr)
                user = profile.user
            except ABHAProfile.DoesNotExist:
                pass

            ABDMSubscription.objects.update_or_create(
                id=sub_id,
                defaults={
                    'abha_address': abha_addr,
                    'status': 'CREATED',
                    'user': user
                }
            )
            logger.info(f"✅ Locker Created: {sub_id}")

    @staticmethod
    def handle_subscription_modified(payload):
        sub_details = payload.get('subscription_details', {})
        sub_id = sub_details.get('subscription_id')
        abha_addr = payload.get('abha_address')
        
        if sub_id:
            defaults = {
                'status': sub_details.get('status'),
                'categories': sub_details.get('categories', []),
            }
            
            if abha_addr:
                try:
                    profile = ABHAProfile.objects.get(abha_address=abha_addr)
                    defaults['user'] = profile.user
                    defaults['abha_address'] = abha_addr
                except ABHAProfile.DoesNotExist:
                    pass
            
            period = sub_details.get('period', {})
            if period.get('from'):
                defaults['period_from'] = parse(period.get('from'))
            if period.get('to'):
                defaults['period_to'] = parse(period.get('to'))
            
            ABDMSubscription.objects.update_or_create(
                id=sub_id,
                defaults=defaults
            )
            logger.info(f"✅ Subscription Updated: {sub_id}")

    @staticmethod
    def handle_subscription_notify(payload):
        subscription_meta = payload.get('subscription_meta', {})
        care_contexts = subscription_meta.get('care_contexts', [])
        hip_id = subscription_meta.get('hip_id')
        logger.info(f"🔔 Notification: {len(care_contexts)} Contexts from HIP {hip_id}")
        # Logic to trigger consent request or notify user

    # ==================== HIP EVENT HANDLERS (New) ====================

    @staticmethod
    def handle_discovery(payload):
        """
        abha.care_context_discover
        Search for patient records based on identifiers (Mobile/ABHA)
        """
        identifiers = payload.get('identifiers', [])
        mobile = None
        for idf in identifiers:
            if idf.get('type') == 'MOBILE':
                mobile = idf.get('value')
        
        if mobile:
            logger.info(f"🔍 Discovery Request for Mobile: {mobile}")
            # TODO: Search local DB (PatientProfile) matching mobile
            # TODO: Call Eka 'on-discover' API to return matched contexts
        else:
            logger.warning("Discovery Request missing Mobile Identifier")

    @staticmethod
    def handle_link_init(payload):
        """
        abha.care.context_discover_link_init
        Generate OTP for linking
        """
        txn_id = payload.get('txn_id')
        patient_data = payload.get('patient', [])
        logger.info(f"🔗 Link Init Request: Txn {txn_id}")
        # TODO: Generate OTP, store mapped to txn_id
        # TODO: Send OTP to user's mobile (Resend OTP API?)
        # TODO: Call Eka 'on-init' API

    @staticmethod
    def handle_link_confirm(payload):
        """
        abha.context_discover_link_confirm
        Verify OTP and Link
        """
        txn_id = payload.get('transaction_id') or payload.get('txn_id') # Payload inconsistency check
        token = payload.get('token') # OTP
        logger.info(f"🔐 Link Confirm Request: Txn {txn_id} OTP {token}")
        # TODO: Verify OTP
        # TODO: If valid, mark contexts as linked
        # TODO: Call Eka 'on-confirm' API

    @staticmethod
    def handle_profile_share(payload):
        """
        abha.hip_profile_share
        Scan & Share: User shared profile at counter
        """
        data = payload # Payload is directly inside 'data' usually
        abha_addr = data.get('abha_address')
        profile_data = data # Contains name, gender, etc.
        logger.info(f"📲 Profile Share Received: {abha_addr}")
        # TODO: Create/Update Patient Record locally
        # TODO: Generate 'Token Number' and return via callback?

    @staticmethod
    def handle_data_fetch(payload):
        """
        abha.hip_data_fetch
        HIU requests data. We must bundle FHIR.
        """
        txn_id = payload.get('transaction_id')
        care_contexts = payload.get('care_contexts', [])
        logger.info(f"📦 Data Fetch Request: {txn_id} for {len(care_contexts)} contexts")
        # TODO: Fetch Documents
        # TODO: Convert to FHIR
        # TODO: Encrypt using 'key_information'
        # TODO: Push to HIU via Data Push API
