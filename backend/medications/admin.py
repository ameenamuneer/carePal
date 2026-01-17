from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Medication, MedicationSchedule, MedicationAdherence,
    MedicationEscalation, MedicationInteraction, MedicationRefill,
    MedicationAdherencePattern
)


class MedicationScheduleInline(admin.TabularInline):
    model = MedicationSchedule
    extra = 1
    fields = ['time_of_day', 'time_label', 'with_food', 'reminder_enabled', 'is_active']


@admin.register(Medication)
class MedicationAdmin(admin.ModelAdmin):
    list_display = [
        'medication_name', 'patient', 'dosage', 'frequency',
        'start_date', 'end_date', 'status_badge', 'is_critical',
        'needs_refill_badge'
    ]
    list_filter = ['status', 'form', 'route', 'is_critical', 'start_date']
    search_fields = [
        'medication_name', 'generic_name', 'brand_name',
        'patient__user__first_name', 'patient__user__last_name'
    ]
    readonly_fields = ['created_at', 'updated_at', 'is_active', 'needs_refill']
    date_hierarchy = 'start_date'
    inlines = [MedicationScheduleInline]
    
    fieldsets = (
        ('Patient', {
            'fields': ('patient',)
        }),
        ('Medication Details', {
            'fields': (
                'medication_name', 'generic_name', 'brand_name',
                'dosage', 'form', 'route'
            )
        }),
        ('Schedule', {
            'fields': (
                'frequency', 'times_per_day', 'start_date', 
                'end_date', 'duration_days'
            )
        }),
        ('Instructions', {
            'fields': ('instructions', 'special_instructions', 'purpose')
        }),
        ('Prescription', {
            'fields': (
                'prescribed_by', 'prescription_number', 'prescribed_date'
            )
        }),
        ('Inventory', {
            'fields': (
                'quantity_prescribed', 'quantity_remaining',
                'refills_allowed', 'refills_remaining', 'needs_refill'
            )
        }),
        ('Status', {
            'fields': (
                'status', 'is_critical', 'is_active',
                'discontinuation_reason', 'discontinued_by', 'discontinued_at'
            )
        }),
        ('Additional Information', {
            'fields': ('side_effects', 'interactions')
        }),
        ('Audit', {
            'fields': ('created_by', 'created_at', 'updated_at')
        }),
    )
    
    def status_badge(self, obj):
        colors = {
            'ACTIVE': 'green',
            'COMPLETED': 'blue',
            'DISCONTINUED': 'red',
            'ON_HOLD': 'orange'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">●</span> {}',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def needs_refill_badge(self, obj):
        if obj.needs_refill:
            return format_html('<span style="color: red;">⚠ Needs Refill</span>')
        return format_html('<span style="color: green;">✓ OK</span>')
    needs_refill_badge.short_description = 'Refill Status'


@admin.register(MedicationSchedule)
class MedicationScheduleAdmin(admin.ModelAdmin):
    list_display = [
        'medication', 'time_of_day', 'time_label',
        'with_food', 'reminder_enabled', 'is_active'
    ]
    list_filter = ['with_food', 'reminder_enabled', 'is_active']
    search_fields = ['medication__medication_name', 'time_label']


@admin.register(MedicationAdherence)
class MedicationAdherenceAdmin(admin.ModelAdmin):
    list_display = [
        'medication', 'scheduled_date', 'scheduled_time',
        'status_colored', 'confirmed_by_patient', 'is_overdue_badge'
    ]
    list_filter = ['status', 'scheduled_date', 'confirmed_by_patient']
    search_fields = ['medication__medication_name']
    readonly_fields = ['is_overdue', 'delay_minutes', 'created_at', 'updated_at']
    date_hierarchy = 'scheduled_date'
    
    fieldsets = (
        ('Medication', {
            'fields': ('medication', 'schedule')
        }),
        ('Schedule', {
            'fields': (
                'scheduled_date', 'scheduled_time', 'scheduled_datetime'
            )
        }),
        ('Actual', {
            'fields': (
                'actual_datetime', 'status', 'confirmed_by_patient',
                'confirmation_method'
            )
        }),
        ('Reasons', {
            'fields': ('skip_reason', 'miss_reason', 'notes')
        }),
        ('Side Effects', {
            'fields': ('side_effects_reported',)
        }),
        ('Reminders', {
            'fields': ('reminder_sent_at', 'reminder_count')
        }),
        ('Status', {
            'fields': ('is_overdue', 'delay_minutes')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def status_colored(self, obj):
        colors = {
            'SCHEDULED': 'blue',
            'TAKEN': 'green',
            'MISSED': 'red',
            'SKIPPED': 'orange',
            'DELAYED': 'yellow'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">●</span> {}',
            color, obj.get_status_display()
        )
    status_colored.short_description = 'Status'
    
    def is_overdue_badge(self, obj):
        if obj.is_overdue:
            return format_html('<span style="color: red;">⚠ Overdue</span>')
        return '-'
    is_overdue_badge.short_description = 'Overdue'


@admin.register(MedicationEscalation)
class MedicationEscalationAdmin(admin.ModelAdmin):
    list_display = [
        'medication', 'action_taken', 'consecutive_misses',
        'successful', 'response_received', 'created_at'
    ]
    list_filter = ['action_taken', 'successful', 'response_received', 'created_at']
    search_fields = ['medication__medication_name', 'escalation_reason']
    readonly_fields = ['created_at']


@admin.register(MedicationInteraction)
class MedicationInteractionAdmin(admin.ModelAdmin):
    list_display = [
        'medication_1', 'medication_2', 'severity_badge',
        'acknowledged_by', 'is_active'
    ]
    list_filter = ['severity', 'is_active', 'acknowledged_at']
    search_fields = [
        'medication_1__medication_name', 'medication_2__medication_name',
        'description'
    ]
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('Medications', {
            'fields': ('medication_1', 'medication_2')
        }),
        ('Interaction Details', {
            'fields': ('severity', 'description', 'clinical_effects', 'management')
        }),
        ('Acknowledgment', {
            'fields': (
                'acknowledged_by', 'acknowledged_at', 'override_reason'
            )
        }),
        ('Status', {
            'fields': ('is_active', 'created_at')
        }),
    )
    
    def severity_badge(self, obj):
        colors = {
            'MILD': 'green',
            'MODERATE': 'orange',
            'SEVERE': 'red',
            'CONTRAINDICATED': 'darkred'
        }
        color = colors.get(obj.severity, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">●</span> {}',
            color, obj.get_severity_display()
        )
    severity_badge.short_description = 'Severity'


@admin.register(MedicationRefill)
class MedicationRefillAdmin(admin.ModelAdmin):
    list_display = [
        'medication', 'requested_date', 'quantity',
        'status_badge', 'pharmacy_name', 'approved_by'
    ]
    list_filter = ['status', 'requested_date', 'filled_date']
    search_fields = ['medication__medication_name', 'pharmacy_name']
    readonly_fields = ['requested_date', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Medication', {
            'fields': ('medication', 'quantity')
        }),
        ('Request', {
            'fields': ('requested_date', 'requested_by')
        }),
        ('Pharmacy', {
            'fields': ('pharmacy_name', 'pharmacy_phone')
        }),
        ('Status', {
            'fields': ('status', 'notes', 'cancellation_reason')
        }),
        ('Fulfillment', {
            'fields': (
                'approved_by', 'approved_at', 'filled_date', 'pickup_date'
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def status_badge(self, obj):
        colors = {
            'REQUESTED': 'blue',
            'APPROVED': 'green',
            'FILLED': 'darkgreen',
            'READY': 'orange',
            'PICKED_UP': 'gray',
            'CANCELLED': 'red'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">●</span> {}',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'




@admin.register(MedicationAdherencePattern)
class MedicationAdherencePatternAdmin(admin.ModelAdmin):
    list_display = [
        'patient', 'medication', 'period_label',
        'adherence_rate', 'total_scheduled', 'total_taken',
        'total_missed', 'computed_at'
    ]
    list_filter = ['period_label', 'computed_at']
    search_fields = ['patient__user__first_name', 'medication__medication_name']
    readonly_fields = ['computed_at']
