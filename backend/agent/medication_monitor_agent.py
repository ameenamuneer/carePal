import logging
from datetime import date, timedelta

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are the CarePal Medication Monitor Agent. You receive a medication-related activity log
from a patient's conversation with the CarePal Live AI assistant, along with full context
about the patient's medication schedule and today's adherence records.

Your job is to decide ONE action from the four available tools:

1. update_adherence — patient confirmed taking or skipping a specific dose today
2. update_medication_times — patient wants to permanently change WHEN they take a medication
3. request_clarification — the log is genuinely ambiguous; queue a question for Live AI
4. do_nothing — not enough information and clarification is not warranted

## Deciding which tool to use

### update_adherence
Use when the patient has clearly stated they took or skipped a specific dose TODAY.
- Check the adherence context: if that slot is already TAKEN or SKIPPED, use do_nothing.
- Confidence must be ≥ 0.6 or use request_clarification instead.

### update_medication_times
Use ONLY when the patient expresses a PERMANENT preference to change dose timing.
Examples that qualify:
  "I want to take my morning pill at 7am from now on"
  "Can we move my evening dose to 9pm?"
  "I prefer taking Meftal at night instead of morning"
Examples that do NOT qualify (one-off lateness, not a preference change):
  "I took it a bit late today"
  "I forgot to take it this morning"
Rules:
  - The new_times list length must match the medication's frequency
    (TWICE_DAILY needs exactly 2 times, ONCE_DAILY needs 1, etc.)
  - Times in HH:MM 24-hour format.
  - Past adherence records are NEVER affected — only future schedule calculations change.

### request_clarification
Use when the log is ambiguous AND a specific direct question would resolve it.
Do NOT use for vague uncertainty. Only queue questions that are genuinely necessary.

### do_nothing
Use when the log contains no actionable medication event and clarification is unwarranted.

## General rules
- Match medication names loosely: "my blood pressure pill" → the antihypertensive on schedule.
  "my pill" alone with multiple medications → too vague → request_clarification.
- NEVER modify past records. NEVER act on logs from previous days.
- You must call exactly one tool. Do not respond with plain text.
"""

TOOLS = [
    {
        "name": "update_adherence",
        "description": (
            "Update or create a MedicationAdherence record for a specific medication. "
            "Only call this when you are confident the log refers to a specific medication "
            "on today's schedule AND that schedule slot has not already been recorded. "
            "Do NOT call if an adherence record for this medication and time slot already exists "
            "with status TAKEN or SKIPPED — duplication must be avoided."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "medication_name": {
                    "type": "string",
                    "description": "Exact or closest matching name from the active medications list."
                },
                "status": {
                    "type": "string",
                    "enum": ["TAKEN", "SKIPPED", "PARTIAL"],
                    "description": (
                        "TAKEN: patient confirmed they took it. "
                        "SKIPPED: patient explicitly refused or said they are not taking it. "
                        "PARTIAL: patient took only part of the dose."
                    )
                },
                "notes": {
                    "type": "string",
                    "description": "Brief note summarising what the patient said."
                },
                "confidence": {
                    "type": "number",
                    "description": (
                        "Your confidence that this action is correct, 0.0 to 1.0. "
                        "If below 0.6, use request_clarification instead."
                    )
                }
            },
            "required": ["medication_name", "status", "confidence"]
        }
    },
    {
        "name": "request_clarification",
        "description": (
            "Queue a follow-up question to be asked by the Live AI in the next session. "
            "Use this when the log is ambiguous — you cannot confidently identify which "
            "medication was taken, whether it was taken or skipped, or when. "
            "Do NOT use this if the log is clear enough to act on."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The question for the Live AI to ask the patient naturally."
                },
                "context": {
                    "type": "string",
                    "description": "Internal context (not shown to patient) explaining why this is being asked."
                },
                "priority": {
                    "type": "integer",
                    "description": "1 (urgent, ask immediately) to 10 (low priority). Default 5."
                }
            },
            "required": ["question", "context"]
        }
    },
    {
        "name": "update_medication_times",
        "description": (
            "Update the preferred dosing times for a specific medication. "
            "Use this ONLY when the patient has clearly expressed a desire to permanently change "
            "the time they take a medication (e.g. 'I want to take my morning pill at 7am instead of 8am'). "
            "This updates the medication's stored dose_times. Future schedule calculations will use the new times. "
            "Past adherence records are NEVER modified. "
            "Do NOT use this for one-off late/missed doses — use update_adherence for those."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "medication_name": {
                    "type": "string",
                    "description": "Exact or closest matching name from the active medications list."
                },
                "new_times": {
                    "type": "array",
                    "description": "New dosing times. Must match the medication's frequency (e.g. TWICE_DAILY needs 2 times).",
                    "items": {
                        "type": "object",
                        "properties": {
                            "time": {
                                "type": "string",
                                "description": "HH:MM in 24-hour format, e.g. '07:00'"
                            },
                            "label": {
                                "type": "string",
                                "description": "Human-readable label, e.g. 'Morning', 'Evening', 'With dinner'"
                            }
                        },
                        "required": ["time", "label"]
                    }
                },
                "reason": {
                    "type": "string",
                    "description": "Brief note explaining the change (patient preference, doctor instruction, etc.)"
                }
            },
            "required": ["medication_name", "new_times"]
        }
    },
    {
        "name": "do_nothing",
        "description": (
            "Take no action. Use this when the log does not contain enough information "
            "to update adherence AND clarification is not warranted."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Brief internal reason for taking no action."
                }
            },
            "required": ["reason"]
        }
    }
]


class MedicationMonitorAgent:

    def __init__(self):
        from google import genai
        self.client = genai.Client(api_key=self._get_api_key())

    def _get_api_key(self) -> str:
        import os
        return (
            os.environ.get('GOOGLE_API_KEY')
            or getattr(settings, 'GOOGLE_API_KEY', None)
            or getattr(settings, 'GEMINI_API_KEY', None)
            or os.environ.get('GEMINI_API_KEY', '')
        )

    def process(self, log) -> None:
        from google import genai
        from google.genai import types as gtypes

        context = self._build_context(log)

        function_declarations = []
        for t in TOOLS:
            function_declarations.append(
                gtypes.FunctionDeclaration(
                    name=t['name'],
                    description=t['description'],
                    parameters=gtypes.Schema(
                        type='OBJECT',
                        properties={
                            k: gtypes.Schema(
                                type=v.get('type', 'STRING').upper(),
                                description=v.get('description', ''),
                                enum=v.get('enum'),
                            )
                            for k, v in t['parameters']['properties'].items()
                        },
                        required=t['parameters'].get('required', []),
                    )
                )
            )

        try:
            response = self.client.models.generate_content(
                model='gemini-2.0-flash',
                contents=context,
                config=gtypes.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    tools=[gtypes.Tool(function_declarations=function_declarations)],
                    tool_config=gtypes.ToolConfig(
                        function_calling_config=gtypes.FunctionCallingConfig(
                            mode='ANY',
                        )
                    ),
                    temperature=0.1,
                ),
            )

            for part in response.candidates[0].content.parts:
                if part.function_call:
                    self._dispatch(part.function_call, log)
                    break
            else:
                logger.warning(f"[MedAgent] No function call in response for log {log.id}")

        except Exception as e:
            logger.error(f"[MedAgent] Gemini call failed for log {log.id}: {e}")
            raise

    def _dispatch(self, fc, log) -> None:
        args = dict(fc.args)
        logger.info(f"[MedAgent] Tool called: {fc.name} | args: {args} | log: {log.id}")

        if fc.name == 'update_adherence':
            self._update_adherence(
                log=log,
                medication_name=args['medication_name'],
                status=args['status'],
                notes=args.get('notes', ''),
                confidence=float(args.get('confidence', 1.0)),
            )
        elif fc.name == 'request_clarification':
            self._queue_clarification(
                log=log,
                question=args['question'],
                context=args.get('context', ''),
                priority=int(args.get('priority', 5)),
            )
        elif fc.name == 'update_medication_times':
            self._update_medication_times(
                log=log,
                medication_name=args['medication_name'],
                new_times=list(args['new_times']),
                reason=args.get('reason', ''),
            )
        elif fc.name == 'do_nothing':
            logger.info(f"[MedAgent] do_nothing for log {log.id}: {args.get('reason', '')}")

    def _update_adherence(self, log, medication_name: str, status: str, notes: str, confidence: float) -> None:
        from medications.models import Medication, MedicationAdherence
        from medications.schedule_utils import get_times_for_medication

        if confidence < 0.6:
            logger.warning(
                f"[MedAgent] Skipping update for log {log.id} — confidence {confidence} below 0.6"
            )
            return

        patient = log.patient
        today = date.today()

        med = (
            Medication.objects.filter(
                patient=patient,
                medication_name__iexact=medication_name,
                status='ACTIVE',
            ).first()
            or Medication.objects.filter(
                patient=patient,
                medication_name__icontains=medication_name,
                status='ACTIVE',
            ).first()
        )
        if not med:
            logger.warning(f"[MedAgent] Medication not found: '{medication_name}' for patient {patient.id}")
            return

        # Duplicate guard
        existing = MedicationAdherence.objects.filter(
            medication=med,
            scheduled_date=today,
            status__in=['TAKEN', 'SKIPPED'],
        ).first()
        if existing:
            logger.info(
                f"[MedAgent] Skipping — adherence already {existing.status} "
                f"for {med.medication_name} today"
            )
            return

        # Use first scheduled time from dose_times (or frequency default)
        times = get_times_for_medication(med)
        scheduled_time = times[0][0] if times else None

        adherence, created = MedicationAdherence.objects.get_or_create(
            medication=med,
            scheduled_date=today,
            defaults={
                'scheduled_time': scheduled_time,
                'status': status,
                'actual_datetime': log.observed_at,
                'confirmation_method': 'MONITOR_AGENT',
                'notes': notes,
                'source_activity_log': log,
            },
        )
        if not created:
            adherence.status = status
            adherence.actual_datetime = log.observed_at
            adherence.confirmation_method = 'MONITOR_AGENT'
            adherence.notes = notes
            adherence.source_activity_log = log
            adherence.save(update_fields=[
                'status', 'actual_datetime', 'confirmation_method',
                'notes', 'source_activity_log',
            ])

        logger.info(
            f"[MedAgent] {'Created' if created else 'Updated'} adherence: "
            f"{med.medication_name} → {status} (confidence={confidence}, log={log.id})"
        )

    def _update_medication_times(self, log, medication_name: str, new_times: list, reason: str) -> None:
        """
        Update a medication's stored dose_times based on patient preference expressed via Live AI.
        Only affects future schedule calculations — past adherence records are untouched.
        """
        from medications.models import Medication

        patient = log.patient
        # Match by name (case-insensitive)
        med = (
            Medication.objects
            .filter(patient=patient, status='ACTIVE')
            .filter(medication_name__icontains=medication_name)
            .first()
        )
        if not med:
            logger.warning(f"[MedAgent] update_medication_times: no active med matching '{medication_name}' for patient {patient.id}")
            return

        # Validate: new_times must be a list of {time, label} dicts
        validated = []
        for entry in new_times:
            t_str = str(entry.get('time', '')).strip()
            label = str(entry.get('label', '')).strip()
            # Accept HH:MM or HH:MM:SS
            parts = t_str.split(':')
            if len(parts) < 2:
                logger.warning(f"[MedAgent] Invalid time entry '{entry}' — skipping")
                continue
            validated.append({'time': f"{int(parts[0]):02d}:{int(parts[1]):02d}", 'label': label})

        if not validated:
            logger.warning(f"[MedAgent] update_medication_times: no valid times provided for med {med.id}")
            return

        old_times = med.dose_times
        med.dose_times = validated
        med.save(update_fields=['dose_times', 'updated_at'])

        logger.info(
            f"[MedAgent] Updated dose_times for '{med.medication_name}' (id={med.id}) "
            f"from {old_times} to {validated}. Reason: {reason}"
        )
        # No pre-generation needed — schedule is fully lazy.
        # The next time any future date is queried, ensure_adherence_records
        # will calculate times fresh from the updated dose_times.

    def _queue_clarification(self, log, question: str, context: str, priority: int) -> None:
        from .models import PendingQuestion

        PendingQuestion.objects.create(
            patient=log.patient,
            question=question,
            context=context,
            source='MEDICATION_AGENT',
            source_object_type='PatientActivityLog',
            source_object_id=log.id,
            priority=priority,
            expires_at=timezone.now() + timedelta(hours=12),
        )
        logger.info(f"[MedAgent] Queued clarification for log {log.id}: '{question}'")

    def _build_context(self, log) -> str:
        from medications.models import Medication, MedicationAdherence
        from medications.schedule_utils import get_times_for_medication
        from .models import PatientActivityLog

        patient = log.patient
        today = date.today()

        meds = Medication.objects.filter(patient=patient, status='ACTIVE')
        med_lines = []
        for med in meds:
            times_list = get_times_for_medication(med)
            times = ', '.join(f"{t.strftime('%H:%M')} ({label})" for t, label in times_list) or 'no fixed time'
            med_lines.append(
                f"  - {med.medication_name} | dose: {med.dosage} | "
                f"times: {times} | frequency: {med.frequency}"
            )

        adherence_today = MedicationAdherence.objects.filter(
            medication__patient=patient,
            scheduled_date=today,
        ).select_related('medication')
        adherence_lines = [
            f"  - {a.medication.medication_name}: {a.status} "
            f"(recorded at {a.actual_datetime}, method: {a.confirmation_method})"
            for a in adherence_today
        ]

        recent_logs = PatientActivityLog.objects.filter(
            patient=patient,
            activity_type='MEDICATION',
        ).exclude(id=log.id).order_by('-observed_at')[:3]
        recent_lines = [
            f"  - [{r.observed_at.strftime('%H:%M')}] {r.description}"
            for r in recent_logs
        ]

        return f"""PATIENT: {patient.user.get_full_name()}
DATE: {today}
TIME OF LOG: {log.observed_at.strftime('%Y-%m-%d %H:%M')}

WHAT THE PATIENT SAID (activity log description):
"{log.description}"

ACTIVE MEDICATIONS ON SCHEDULE TODAY:
{chr(10).join(med_lines) or '  (none)'}

TODAY\'S ADHERENCE RECORDS ALREADY WRITTEN:
{chr(10).join(adherence_lines) or '  (none yet)'}

RECENT MEDICATION ACTIVITY LOGS (last 3, excluding this one):
{chr(10).join(recent_lines) or '  (none)'}
"""
