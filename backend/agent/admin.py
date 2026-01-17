from django.contrib import admin
from .models import (
    AgentSession,
    AgentMessage,
    AgentAction,
    AgentMemory,
    AgentEventLog,
    AgentCacheEntry
)

@admin.register(AgentSession)
class AgentSessionAdmin(admin.ModelAdmin):
    list_display = ['session_id', 'patient', 'session_type', 'status', 'started_at', 'estimated_cost_usd']
    list_filter = ['session_type', 'status', 'language']
    search_fields = ['session_id', 'patient__user__first_name', 'patient__user__last_name']
    readonly_fields = ['session_id', 'started_at', 'estimated_cost_usd']

@admin.register(AgentMessage)
class AgentMessageAdmin(admin.ModelAdmin):
    list_display = ['session', 'sender', 'message_type', 'timestamp']
    list_filter = ['sender', 'message_type']
    search_fields = ['content']

@admin.register(AgentAction)
class AgentActionAdmin(admin.ModelAdmin):
    list_display = ['session', 'action_type', 'function_called', 'status', 'created_at']
    list_filter = ['action_type', 'status']
    readonly_fields = ['created_at', 'executed_at']

@admin.register(AgentMemory)
class AgentMemoryAdmin(admin.ModelAdmin):
    list_display = ['patient', 'memory_type', 'key', 'is_active', 'access_count']
    list_filter = ['memory_type', 'is_active']
    search_fields = ['key', 'content']

@admin.register(AgentEventLog)
class AgentEventLogAdmin(admin.ModelAdmin):
    list_display = ['patient', 'event_type', 'severity', 'timestamp']
    list_filter = ['event_type', 'severity']
    date_hierarchy = 'timestamp'

@admin.register(AgentCacheEntry)
class AgentCacheEntryAdmin(admin.ModelAdmin):
    list_display = ['cache_key', 'patient', 'hit_count', 'cost_saved_usd', 'expires_at']
    readonly_fields = ['created_at', 'hit_count', 'cost_saved_usd']
