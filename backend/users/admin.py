from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

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
