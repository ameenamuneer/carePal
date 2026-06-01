"""
Function Calling Definitions for Gemini
These are the tools the AI agent can use to interact with CarePAL
"""

import google.generativeai as genai
from typing import List, Dict, Any


# Function definitions in Gemini format
FUNCTION_DECLARATIONS = [
    {
        "name": "create_alert",
        "description": "Create a health alert for the patient. Use when patient reports concerning symptoms or when vitals are abnormal.",
        "parameters": {
            "type": "object",
            "properties": {
                "severity": {
                    "type": "string",
                    "description": "Alert severity level",
                    "enum": ["INFO", "WARNING", "CRITICAL", "EMERGENCY"]
                },
                "title": {
                    "type": "string",
                    "description": "Short alert title"
                },
                "message": {
                    "type": "string",
                    "description": "Detailed alert message"
                },
                "alert_type": {
                    "type": "string",
                    "description": "Type of alert",
                    "enum": [
                        "VITAL_ANOMALY",
                        "SYMPTOM_REPORT",
                        "MEDICATION_MISSED",
                        "FALL_DETECTED",
                        "EMERGENCY",
                        "DEVICE_ISSUE",
                        "GENERAL"
                    ]
                }
            },
            "required": ["severity", "title", "message"]
        }
    },
    {
        "name": "record_vital_reading",
        "description": "Record a vital sign reading shared by the patient",
        "parameters": {
            "type": "object",
            "properties": {
                "vital_type": {
                    "type": "string",
                    "description": "Type of vital sign",
                    "enum": ["BP", "HR", "SPO2", "TEMP", "GLUCOSE", "WEIGHT", "RR"]
                },
                "value": {
                    "type": "number",
                    "description": "Single value (for HR, SPO2, etc.)"
                },
                "systolic": {
                    "type": "number",
                    "description": "Systolic blood pressure (for BP only)"
                },
                "diastolic": {
                    "type": "number",
                    "description": "Diastolic blood pressure (for BP only)"
                },
                "notes": {
                    "type": "string",
                    "description": "Additional notes about the reading"
                }
            },
            "required": ["vital_type"]
        }
    },
    {
        "name": "get_medication_schedule",
        "description": "Get the patient's medication schedule for today",
        "parameters": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "Date in YYYY-MM-DD format (default: today)"
                }
            }
        }
    },
    {
        "name": "call_emergency_contact",
        "description": "Initiate an emergency call to patient's emergency contact. Use only for serious/emergency situations.",
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Reason for emergency call"
                },
                "urgency": {
                    "type": "string",
                    "description": "Urgency level",
                    "enum": ["HIGH", "CRITICAL"]
                }
            },
            "required": ["reason", "urgency"]
        }
    },
    {
        "name": "call_family_member",
        "description": "Initiate a call to a family member to inform about patient status",
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Reason for calling family"
                },
                "message": {
                    "type": "string",
                    "description": "Message to convey to family"
                }
            },
            "required": ["reason", "message"]
        }
    },
    {
        "name": "send_sms_notification",
        "description": "Send an SMS notification to family member or emergency contact",
        "parameters": {
            "type": "object",
            "properties": {
                "recipient_type": {
                    "type": "string",
                    "description": "Who to send SMS to",
                    "enum": ["EMERGENCY_CONTACT", "FAMILY_MEMBER", "PRIMARY_FAMILY"]
                },
                "message": {
                    "type": "string",
                    "description": "SMS message content"
                }
            },
            "required": ["recipient_type", "message"]
        }
    },
    {
        "name": "log_patient_activity",
        "description": (
            "Proactively log any patient activity, behaviour, or health observation you notice "
            "during natural conversation — without being asked. Use this whenever you observe: "
            "meals eaten, exercise done or skipped, reported symptoms, mood changes, sleep patterns, "
            "medication-related comments, social interactions, environmental notes, or any pattern "
            "that deviates from the patient's usual routine. Log immediately after the observation "
            "is clear. Do NOT wait for the patient to finish speaking."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "activity_type": {
                    "type": "string",
                    "description": "Category of the activity or observation",
                    "enum": [
                        "MEAL", "EXERCISE", "SLEEP", "SYMPTOM", "MEDICATION",
                        "MOOD", "VITAL_OBSERVATION", "BEHAVIOR", "SOCIAL",
                        "ENVIRONMENT", "OTHER"
                    ]
                },
                "description": {
                    "type": "string",
                    "description": (
                        "A clear, timestamped natural-language log entry. "
                        "Examples: 'Patient had lunch at 2:30 pm', "
                        "'Reported dizziness when standing up', "
                        "'Did not go for the usual morning walk today'."
                    )
                },
                "details": {
                    "type": "object",
                    "description": (
                        "Optional structured details. For MEAL: {meal_items, appetite}. "
                        "For SYMPTOM: {symptom_name, severity, duration, body_part}. "
                        "For EXERCISE: {activity_name, duration_minutes, intensity}. "
                        "For SLEEP: {hours_slept, quality}. "
                        "For MOOD: {mood_description, energy_level}."
                    )
                },
                "observed_at": {
                    "type": "string",
                    "description": (
                        "ISO-8601 datetime when the activity occurred, if the patient mentioned "
                        "a specific time (e.g. '2:30 pm'). Leave blank to default to now."
                    )
                },
                "is_notable": {
                    "type": "boolean",
                    "description": (
                        "Set true if this deviates from the patient's usual pattern, "
                        "is clinically significant, or warrants caregiver attention."
                    )
                },
                "notable_reason": {
                    "type": "string",
                    "description": "Explain why it is notable (only when is_notable is true)."
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Short keyword tags for easy filtering (e.g. ['dizziness', 'skipped_walk'])."
                },
                "ai_confidence": {
                    "type": "string",
                    "description": "How confident you are in this observation.",
                    "enum": ["HIGH", "MEDIUM", "LOW"]
                }
            },
            "required": ["activity_type", "description"]
        }
    },
    {
        "name": "get_patient_vitals_summary",
        "description": "Get summary of patient's recent vital signs",
        "parameters": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "Number of days to look back (default: 7)"
                },
                "vital_type": {
                    "type": "string",
                    "description": "Specific vital to get, or 'all'",
                    "enum": ["all", "BP", "HR", "SPO2", "TEMP", "GLUCOSE"]
                }
            }
        }
    },
    {
        "name": "check_medication_adherence",
        "description": "Check if patient is adhering to medication schedule",
        "parameters": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "Number of days to check (default: 7)"
                }
            }
        }
    },
    {
        "name": "update_patient_notes",
        "description": "Add notes to patient's medical record",
        "parameters": {
            "type": "object",
            "properties": {
                "note_type": {
                    "type": "string",
                    "description": "Type of note",
                    "enum": ["OBSERVATION", "CONCERN", "IMPROVEMENT", "GENERAL"]
                },
                "note_text": {
                    "type": "string",
                    "description": "The note content"
                }
            },
            "required": ["note_type", "note_text"]
        }
    },
    {
        "name": "schedule_task",
        "description": "Schedule a future task or reminder for patient care",
        "parameters": {
            "type": "object",
            "properties": {
                "task_type": {
                    "type": "string",
                    "description": "Type of task",
                    "enum": ["MEDICATION_REFILL", "DOCTOR_APPOINTMENT", "FOLLOW_UP", "GENERAL"]
                },
                "title": {
                    "type": "string",
                    "description": "Task title"
                },
                "scheduled_date": {
                    "type": "string",
                    "description": "Date in YYYY-MM-DD format"
                },
                "scheduled_time": {
                    "type": "string",
                    "description": "Time in HH:MM format (24-hour)"
                },
                "description": {
                    "type": "string",
                    "description": "Task description"
                }
            },
            "required": ["task_type", "title", "scheduled_date"]
        }
    },
    {
        "name": "get_health_insights",
        "description": "Get AI-generated health insights based on patient data",
        "parameters": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "Days of data to analyze (default: 30)"
                }
            }
        }
    },
    {
        "name": "escalate_alert",
        "description": "Escalate an existing alert to higher priority or different recipient",
        "parameters": {
            "type": "object",
            "properties": {
                "alert_id": {
                    "type": "integer",
                    "description": "ID of alert to escalate"
                },
                "reason": {
                    "type": "string",
                    "description": "Reason for escalation"
                }
            },
            "required": ["alert_id", "reason"]
        }
    }
]


def get_tools_for_gemini() -> List:
    """
    Get tools in Gemini format for function calling
    """
    return [genai.protos.Tool(function_declarations=FUNCTION_DECLARATIONS)]


def get_tool_config() -> Dict:
    """
    Get tool configuration for Gemini
    """
    return {
        "function_calling_config": {
            "mode": "AUTO",  # Let Gemini decide when to call functions
        }
    }


# Function execution permissions
FUNCTION_PERMISSIONS = {
    "create_alert": {
        "requires_permission": False,  # Can always create alerts
        "critical_threshold": "CRITICAL",  # Escalate if severity >= CRITICAL
    },
    "record_vital_reading": {
        "requires_permission": False,
    },
    "get_medication_schedule": {
        "requires_permission": False,
    },
    "call_emergency_contact": {
        "requires_permission": True,  # Requires confirmation for calls
        "auto_approve_on": "EMERGENCY_severity",  # Auto-approve for emergencies
    },
    "call_family_member": {
        "requires_permission": True,
    },
    "send_sms_notification": {
        "requires_permission": False,  # SMS doesn't require permission
    },
    "log_patient_activity": {
        "requires_permission": False,
    },
    "get_patient_vitals_summary": {
        "requires_permission": False,
    },
    "check_medication_adherence": {
        "requires_permission": False,
    },
    "update_patient_notes": {
        "requires_permission": False,
    },
    "schedule_task": {
        "requires_permission": False,
    },
    "get_health_insights": {
        "requires_permission": False,
    },
    "escalate_alert": {
        "requires_permission": True,
    },
}


def requires_permission(function_name: str, parameters: Dict[str, Any]) -> bool:
    """
    Check if a function call requires user permission
    
    Args:
        function_name: Name of the function
        parameters: Function parameters
    
    Returns:
        True if permission is required
    """
    if function_name not in FUNCTION_PERMISSIONS:
        return True  # Default to requiring permission for unknown functions
    
    config = FUNCTION_PERMISSIONS[function_name]
    
    # Check base permission requirement
    if not config.get("requires_permission", False):
        return False
    
    # Check auto-approve conditions
    auto_approve = config.get("auto_approve_on")
    if auto_approve:
        # Example: auto_approve_on="EMERGENCY_severity"
        if "_" in auto_approve:
            condition_value, condition_key = auto_approve.split("_", 1)
            if parameters.get(condition_key) == condition_value:
                return False
    
    return True
