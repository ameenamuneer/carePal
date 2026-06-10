from rest_framework.permissions import BasePermission
from family.models import FamilyMember
from users.models import ClinicalRelationship


class IsPatient(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.user_type == 'PATIENT'


class IsFamily(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.user_type == 'FAMILY'


class IsDoctor(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.user_type == 'DOCTOR'


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.user_type == 'ADMIN'


class IsFamilyOrDoctor(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.user_type in ('FAMILY', 'DOCTOR', 'ADMIN')


class CanAccessPatientData(BasePermission):
    """
    Object-level permission. Pass a PatientProfile as the object.
    - PATIENT: only their own profile.
    - FAMILY: only linked patients (active FamilyMember).
    - DOCTOR: only linked patients (active ClinicalRelationship).
    - ADMIN: all patients.
    """
    def has_object_permission(self, request, view, obj):
        from patients.models import PatientProfile
        if isinstance(obj, PatientProfile):
            patient = obj
        else:
            patient = getattr(obj, 'patient', None)
        if patient is None:
            return False

        user = request.user
        if user.user_type == 'PATIENT':
            return hasattr(user, 'patient_profile') and user.patient_profile == patient
        if user.user_type == 'FAMILY':
            return FamilyMember.objects.filter(
                user=user, patient=patient, is_active=True
            ).exists()
        if user.user_type == 'DOCTOR':
            return ClinicalRelationship.objects.filter(
                doctor=user, patient=patient, is_active=True
            ).exists()
        if user.user_type == 'ADMIN':
            return True
        return False


def get_accessible_patient_ids(user):
    """Return a queryset of patient PKs this user may access."""
    from patients.models import PatientProfile
    if user.user_type == 'PATIENT':
        if hasattr(user, 'patient_profile'):
            return [user.patient_profile.pk]
        return []
    if user.user_type == 'FAMILY':
        return list(
            FamilyMember.objects.filter(user=user, is_active=True)
            .values_list('patient_id', flat=True)
        )
    if user.user_type == 'DOCTOR':
        return list(
            ClinicalRelationship.objects.filter(doctor=user, is_active=True)
            .values_list('patient_id', flat=True)
        )
    if user.user_type == 'ADMIN':
        return list(PatientProfile.objects.values_list('pk', flat=True))
    return []


# ── per-permission helpers ──────────────────────────────────────────────────

def family_can(user, patient, permission):
    """True if user is an active FamilyMember of patient with the given permission."""
    try:
        fm = FamilyMember.objects.get(user=user, patient=patient, is_active=True)
        return fm.has_permission(permission)
    except FamilyMember.DoesNotExist:
        return False


def doctor_can(user, patient, permission):
    """True if user is an active ClinicalRelationship for patient with the given permission."""
    try:
        cr = ClinicalRelationship.objects.get(doctor=user, patient=patient, is_active=True)
        return cr.has_permission(permission)
    except ClinicalRelationship.DoesNotExist:
        return False
