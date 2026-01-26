# backend/agent/medication_function_definitions.py

MEDICATION_FUNCTIONS = [
    {
        "name": "check_current_medications",
        "description": "Check patient's current medication status including upcoming, overdue, and recently taken medications. Use this to understand medication compliance and what needs attention.",
        "parameters": {
            "type": "object",
            "properties": {
                "patient_id": {
                    "type": "integer",
                    "description": "Patient ID"
                }
            },
            "required": ["patient_id"]
        }
    },
    {
        "name": "mark_medication_taken",
        "description": "Mark a medication as taken when patient confirms they've taken it. Updates the adherence record.",
        "parameters": {
            "type": "object",
            "properties": {
                "adherence_id": {
                    "type": "integer",
                    "description": "Adherence record ID from check_current_medications"
                },
                "confirmation": {
                    "type": "string",
                    "description": "How patient confirmed (e.g., 'Patient said yes', 'Voice confirmation')"
                }
            },
            "required": ["adherence_id"]
        }
    },
    {
        "name": "mark_medication_skipped",
        "description": "Mark a medication as skipped when patient chooses not to take it. Records the reason.",
        "parameters": {
            "type": "object",
            "properties": {
                "adherence_id": {
                    "type": "integer",
                    "description": "Adherence record ID"
                },
                "reason": {
                    "type": "string",
                    "description": "Why the medication was skipped"
                }
            },
            "required": ["adherence_id", "reason"]
        }
    },
    {
        "name": "get_medication_list",
        "description": "Get complete list of patient's active medications with details. Use when patient asks about their medications or you need full context.",
        "parameters": {
            "type": "object",
            "properties": {
                "patient_id": {
                    "type": "integer",
                    "description": "Patient ID"
                }
            },
            "required": ["patient_id"]
        }
    }
]
