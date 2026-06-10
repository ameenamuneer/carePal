import logging
from datetime import date, timedelta

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are the CarePal Medication Monitor Agent. You receive a medication-related activity log
from a patient's conversation with the CarePal Live AI assistant, along with full context
about the patient's medication schedule and today's adherence records.

Your job is to decide ONE action:
1. update_adherence — if you can clearly identify a specific medication dose event
2. request_clarification — if the log is genuinely ambiguous
3. do_nothing — if no action is needed

Rules:
- NEVER mark a medication as TAKEN/SKIPPED if today's adherence record for that
  medication slot already has status TAKEN or SKIPPED. Check the context carefully.
- If the patient mentions the same medication multiple times in recent logs, check
  if adherence was already recorded before acting.
- Prefer do_nothing over a wrong update_adherence call.
- Only use request_clarification when the ambiguity is specific and a direct question
  would resolve it — do not ask vague questions.
- Match medication names loosely: "my blood pressure pill" matches if only one
  antihypertensive is on the schedule. "my pill" alone is too vague.
- A confidence below 0.6 on update_adherence means you should use
  request_clarification or do_nothing instead.
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
        elif fc.name == 'do_nothing':
            logger.info(f"[MedAgent] do_nothing for log {log.id}: {args.get('reason', '')}")

    def _update_adherence(self, log, medication_name: str, status: str, notes: str, confidence: float) -> None:
        from medications.models import Medication, MedicationAdherence, MedicationSchedule

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

        schedule = MedicationSchedule.objects.filter(
            medication=med, is_active=True
        ).first()

        adherence, created = MedicationAdherence.objects.get_or_create(
            medication=med,
            scheduled_date=today,
            defaults={
                'scheduled_time': schedule.time_of_day if schedule else None,
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
        from medications.models import Medication, MedicationAdherence, MedicationSchedule
        from .models import PatientActivityLog

        patient = log.patient
        today = date.today()

        meds = Medication.objects.filter(patient=patient, status='ACTIVE')
        med_lines = []
        for med in meds:
            schedules = MedicationSchedule.objects.filter(
                medication=med, is_active=True
            ).values_list('time_of_day', flat=True)
            times = ', '.join(str(t) for t in schedules) or 'no fixed time'
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
