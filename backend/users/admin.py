from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, ClinicalRelationship

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'user_type', 'phone_number', 'is_active', 'created_at')
    list_filter = ('user_type', 'is_active', 'is_staff')
    fieldsets = UserAdmin.fieldsets + (
        ('Profile', {'fields': ('user_type', 'phone_number', 'date_of_birth', 'profile_picture')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Profile', {'fields': ('user_type', 'phone_number', 'date_of_birth', 'profile_picture')}),
    )
    search_fields = ('username', 'email', 'phone_number', 'first_name', 'last_name')
    ordering = ('-created_at',)


@admin.register(ClinicalRelationship)
class ClinicalRelationshipAdmin(admin.ModelAdmin):
    list_display = (
        'doctor', 'patient', 'role', 'is_active',
        'can_view_vitals', 'can_view_activity_log',
        'can_view_medications', 'can_edit_medications',
        'created_at',
    )
    list_filter = ('role', 'is_active')
    search_fields = ('doctor__first_name', 'doctor__last_name', 'patient__user__first_name', 'patient__user__last_name')
    autocomplete_fields = ['doctor']
    list_editable = ('is_active',)
