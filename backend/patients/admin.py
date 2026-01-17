from django.contrib import admin
from .models import PatientProfile, EmergencyContact, HealthCondition

@admin.register(PatientProfile)
class PatientProfileAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'gender', 'blood_group', 'age_display', 
        'city', 'preferred_language', 'is_active', 'created_at'
    ]
    list_filter = ['gender', 'blood_group', 'preferred_language', 'is_active', 'state']
    search_fields = ['user__first_name', 'user__last_name', 'user__phone_number', 'city']
    readonly_fields = ['created_at', 'updated_at', 'bmi', 'bmi_category']
    
    fieldsets = (
        ('User Information', {
            'fields': ('user',)
        }),
        ('Basic Information', {
            'fields': ('gender', 'blood_group', 'height_cm', 'weight_kg', 'bmi', 'bmi_category')
        }),
        ('Address', {
            'fields': ('address_line1', 'address_line2', 'city', 'state', 'pincode', 'country')
        }),
        ('Health Information', {
            'fields': ('health_conditions', 'allergies', 'current_medications', 'medical_notes', 'last_hospital_visit')
        }),
        ('Preferences', {
            'fields': ('preferred_language',)
        }),
        ('Status', {
            'fields': ('is_active', 'created_at', 'updated_at')
        }),
    )
    
    def age_display(self, obj):
        return obj.user.age if obj.user else None
    age_display.short_description = 'Age'


@admin.register(EmergencyContact)
class EmergencyContactAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'relationship', 'phone_number', 'patient',
        'is_primary', 'priority_order', 'is_active'
    ]
    list_filter = ['relationship', 'is_primary', 'is_active']
    search_fields = ['name', 'phone_number', 'patient__user__first_name']
    ordering = ['patient', 'priority_order']


@admin.register(HealthCondition)
class HealthConditionAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'is_active', 'created_at']
    list_filter = ['category', 'is_active']
    search_fields = ['name', 'description']
