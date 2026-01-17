"""
Enhanced Function Definitions - Comprehensive Data Access
These functions give the AI agent COMPLETE access to patient data
for intelligent, human-like conversations
"""

import google.generativeai as genai
from typing import List, Dict, Any


# ENHANCED FUNCTION DECLARATIONS - Complete Data Access
ENHANCED_FUNCTION_DECLARATIONS = [
    # ==================== PATIENT PROFILE ACCESS ====================
    {
        "name": "get_complete_patient_profile",
        "description": "Get complete patient profile with all details - demographics, conditions, emergency contacts, preferences. Call this at the START of any conversation to have full context.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    
    # ==================== VITAL SIGNS ACCESS ====================
    {
        "name": "get_complete_vitals_history",
        "description": "Get complete vital signs history with trends, anomalies, and patterns. Use to discuss patient's vital readings.",
        "parameters": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "Number of days to look back (default: 30)"
                },
                "vital_types": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific vital types or 'all'"
                },
                "include_trends": {
                    "type": "boolean",
                    "description": "Include trend analysis (default: true)"
                }
            }
        }
    },
    {
        "name": "get_latest_vital_readings",
        "description": "Get the most recent vital sign readings. Use when patient asks 'what was my last blood pressure?'",
        "parameters": {
            "type": "object",
            "properties": {
                "vital_type": {
                    "type": "string",
                    "description": "Specific vital or 'all'",
                    "enum": ["all", "BP", "HR", "SPO2", "TEMP", "GLUCOSE", "WEIGHT", "RR"]
                },
                "count": {
                    "type": "integer",
                    "description": "Number of latest readings (default: 1)"
                }
            }
        }
    },
    
    # ==================== MEDICATION ACCESS ====================
    {
        "name": "get_complete_medication_info",
        "description": "Get complete medication information - active meds, schedules, adherence, side effects, interactions. Use to discuss medications comprehensively.",
        "parameters": {
            "type": "object",
            "properties": {
                "include_history": {
                    "type": "boolean",
                    "description": "Include past medications (default: false)"
                },
                "include_adherence": {
                    "type": "boolean",
                    "description": "Include adherence data (default: true)"
                }
            }
        }
    },
    {
        "name": "get_todays_medication_schedule",
        "description": "Get today's complete medication schedule with status (taken/missed). Use for medication reminders and check-ins.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "get_medication_details",
        "description": "Get detailed information about a specific medication - dosage, purpose, side effects, interactions.",
        "parameters": {
            "type": "object",
            "properties": {
                "medication_name": {
                    "type": "string",
                    "description": "Name of the medication"
                }
            },
            "required": ["medication_name"]
        }
    },
    
    # ==================== ALERTS & HEALTH STATUS ====================
    {
        "name": "get_current_alerts",
        "description": "Get all current active alerts and warnings. Use to understand patient's current health concerns.",
        "parameters": {
            "type": "object",
            "properties": {
                "severity": {
                    "type": "string",
                    "description": "Filter by severity or 'all'",
                    "enum": ["all", "INFO", "WARNING", "CRITICAL", "EMERGENCY"]
                },
                "include_resolved": {
                    "type": "boolean",
                    "description": "Include recently resolved alerts (default: false)"
                }
            }
        }
    },
    {
        "name": "get_health_summary",
        "description": "Get comprehensive health summary - current status, trends, risks, recommendations. Use for overall health discussions.",
        "parameters": {
            "type": "object",
            "properties": {
                "period_days": {
                    "type": "integer",
                    "description": "Time period for summary (default: 7)"
                }
            }
        }
    },
    
    # ==================== ANALYTICS & REPORTS ====================
    {
        "name": "get_health_analytics",
        "description": "Get AI-generated health analytics - insights, patterns, correlations, risk assessment. Use for detailed health discussions.",
        "parameters": {
            "type": "object",
            "properties": {
                "period_days": {
                    "type": "integer",
                    "description": "Analysis period (default: 30)"
                },
                "include_predictions": {
                    "type": "boolean",
                    "description": "Include predictive analytics (default: true)"
                }
            }
        }
    },
    {
        "name": "get_medication_adherence_report",
        "description": "Get detailed medication adherence analysis with patterns and recommendations.",
        "parameters": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "Number of days to analyze (default: 30)"
                }
            }
        }
    },
    
    # ==================== FAMILY & CONTACTS ====================
    {
        "name": "get_family_contacts",
        "description": "Get list of family members and emergency contacts with their preferences and notification settings.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    
    # ==================== CONVERSATION MEMORY ====================
    {
        "name": "get_conversation_history",
        "description": "Get previous conversation history with this patient. Use to maintain continuity.",
        "parameters": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "Days to look back (default: 7)"
                },
                "session_count": {
                    "type": "integer",
                    "description": "Number of recent sessions (default: 5)"
                }
            }
        }
    },
    {
        "name": "get_patient_concerns",
        "description": "Get patient's expressed concerns, worries, and questions from previous conversations.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    
    # ==================== ACTIONS (from original) ====================
    {
        "name": "record_vital_reading",
        "description": "Record a vital sign reading shared by the patient",
        "parameters": {
            "type": "object",
            "properties": {
                "vital_type": {
                    "type": "string",
                    "enum": ["BP", "HR", "SPO2", "TEMP", "GLUCOSE", "WEIGHT", "RR"]
                },
                "value": {"type": "number"},
                "systolic": {"type": "number"},
                "diastolic": {"type": "number"},
                "notes": {"type": "string"}
            },
            "required": ["vital_type"]
        }
    },
    {
        "name": "create_alert",
        "description": "Create a health alert",
        "parameters": {
            "type": "object",
            "properties": {
                "severity": {
                    "type": "string",
                    "enum": ["INFO", "WARNING", "CRITICAL", "EMERGENCY"]
                },
                "title": {"type": "string"},
                "message": {"type": "string"},
                "alert_type": {
                    "type": "string",
                    "enum": ["VITAL_ANOMALY", "SYMPTOM_REPORT", "MEDICATION_MISSED", "EMERGENCY", "GENERAL"]
                }
            },
            "required": ["severity", "title", "message"]
        }
    },
    {
        "name": "call_emergency_contact",
        "description": "Initiate emergency call - ONLY for serious situations",
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {"type": "string"},
                "urgency": {
                    "type": "string",
                    "enum": ["HIGH", "CRITICAL"]
                }
            },
            "required": ["reason", "urgency"]
        }
    },
    {
        "name": "call_family_member",
        "description": "Call a family member to inform about patient status",
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {"type": "string"},
                "message": {"type": "string"}
            },
            "required": ["reason", "message"]
        }
    },
    {
        "name": "send_sms_notification",
        "description": "Send SMS to family/emergency contact",
        "parameters": {
            "type": "object",
            "properties": {
                "recipient_type": {
                    "type": "string",
                    "enum": ["EMERGENCY_CONTACT", "FAMILY_MEMBER", "PRIMARY_FAMILY"]
                },
                "message": {"type": "string"}
            },
            "required": ["recipient_type", "message"]
        }
    },
    {
        "name": "schedule_task",
        "description": "Schedule a future task or reminder",
        "parameters": {
            "type": "object",
            "properties": {
                "task_type": {
                    "type": "string",
                    "enum": ["MEDICATION_REFILL", "DOCTOR_APPOINTMENT", "FOLLOW_UP", "GENERAL"]
                },
                "title": {"type": "string"},
                "scheduled_date": {"type": "string"},
                "scheduled_time": {"type": "string"},
                "description": {"type": "string"}
            },
            "required": ["task_type", "title", "scheduled_date"]
        }
    },
    {
        "name": "update_patient_notes",
        "description": "Add notes to patient record",
        "parameters": {
            "type": "object",
            "properties": {
                "note_type": {
                    "type": "string",
                    "enum": ["OBSERVATION", "CONCERN", "IMPROVEMENT", "GENERAL"]
                },
                "note_text": {"type": "string"}
            },
            "required": ["note_type", "note_text"]
        }
    }
]


def get_enhanced_tools_for_gemini() -> List:
    """
    Get ALL enhanced tools in Gemini format
    This gives the AI agent complete data access for intelligent conversations
    """
    return [genai.protos.Tool(function_declarations=ENHANCED_FUNCTION_DECLARATIONS)]


def get_tool_config() -> Dict:
    """
    Get tool configuration for Gemini
    """
    return {
        "function_calling_config": {
            "mode": "AUTO",  # Let Gemini decide when to call
        }
    }


# PERMISSION SETTINGS
FUNCTION_PERMISSIONS = {
    # DATA ACCESS - No permission needed (read-only)
    "get_complete_patient_profile": {"requires_permission": False},
    "get_complete_vitals_history": {"requires_permission": False},
    "get_latest_vital_readings": {"requires_permission": False},
    "get_complete_medication_info": {"requires_permission": False},
    "get_todays_medication_schedule": {"requires_permission": False},
    "get_medication_details": {"requires_permission": False},
    "get_current_alerts": {"requires_permission": False},
    "get_health_summary": {"requires_permission": False},
    "get_health_analytics": {"requires_permission": False},
    "get_medication_adherence_report": {"requires_permission": False},
    "get_family_contacts": {"requires_permission": False},
    "get_conversation_history": {"requires_permission": False},
    "get_patient_concerns": {"requires_permission": False},
    
    # ACTIONS - Permission as before
    "record_vital_reading": {"requires_permission": False},
    "create_alert": {"requires_permission": False},
    "call_emergency_contact": {
        "requires_permission": True,
        "auto_approve_on": "EMERGENCY_severity"
    },
    "call_family_member": {"requires_permission": True},
    "send_sms_notification": {"requires_permission": False},
    "schedule_task": {"requires_permission": False},
    "update_patient_notes": {"requires_permission": False},
}


def requires_permission(function_name: str, parameters: Dict[str, Any]) -> bool:
    """Check if function requires permission"""
    if function_name not in FUNCTION_PERMISSIONS:
        return True
    
    config = FUNCTION_PERMISSIONS[function_name]
    if not config.get("requires_permission", False):
        return False
    
    # Check auto-approve
    auto_approve = config.get("auto_approve_on")
    if auto_approve and "_" in auto_approve:
        condition_value, condition_key = auto_approve.split("_", 1)
        if parameters.get(condition_key) == condition_value:
            return False
    
    return True
