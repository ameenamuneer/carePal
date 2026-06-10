# CarePal Backend — Remote Viewer & Live AI Enhancement Spec

**Version:** 1.1  
**Date:** 2026-06-10  
**Scope:** Django 4.2 backend at `backend/`  
**Tech stack:** Django 4.2, DRF, Django Channels (WebSocket), Celery + Redis, PostgreSQL, Gemini Live API (gemini-2.5-flash-native-audio-preview)

---

## Table of Contents

1. [Access Control & Account Types](#1-access-control--account-types)
2. [Medication Adherence via Medication Monitor Agent](#2-medication-adherence-via-medication-monitor-agent)
3. [Nutrition Logging (Structured)](#3-nutrition-logging-structured)
4. [Mood Logging (Structured)](#4-mood-logging-structured)
5. [Escalation Timeline](#5-escalation-timeline)
6. [Patient Question Log & Answer Notification](#6-patient-question-log--answer-notification)
7. [Visit Prep Note (AI-Generated)](#7-visit-prep-note-ai-generated)
8. [Task & Schedule Calendar with Live AI Feed](#8-task--schedule-calendar-with-live-ai-feed)
9. [Messaging System](#9-messaging-system)
10. [Push Notification Infrastructure](#10-push-notification-infrastructure)
11. [Family Home Screen — AI-Generated Summary Cards](#11-family-home-screen--ai-generated-summary-cards)

---

## 1. Access Control & Account Types

### Current State

`users.User` has `user_type` field with choices `PATIENT / FAMILY / DOCTOR / ADMIN`. This field is stored but **never checked** by any DRF view or WebSocket consumer. There is no model linking Doctor accounts to PatientProfiles (unlike `family.FamilyMember` which links family users to patients).

---

### 1.1 New Model — `ClinicalRelationship`

**File:** `backend/users/models.py`

Add after the existing `User` model definition.

```python
class ClinicalRelationship(models.Model):
    """
    Links a DOCTOR user to the PatientProfiles they are authorised to view/manage.
    Mirror of family.FamilyMember for the clinical side.
    """
    ROLE_CHOICES = [
        ('PRIMARY', 'Primary Physician'),
        ('SPECIALIST', 'Specialist'),
        ('NURSE', 'Nurse / Paramedic'),
        ('CONSULTANT', 'Consultant'),
    ]

    doctor = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='clinical_relationships',
        limit_choices_to={'user_type': 'DOCTOR'},
    )
    patient = models.ForeignKey(
        'patients.PatientProfile',
        on_delete=models.CASCADE,
        related_name='clinical_relationships',
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='PRIMARY')
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'clinical_relationships'
        unique_together = ['doctor', 'patient']

    def __str__(self):
        return f"Dr {self.doctor.get_full_name()} → {self.patient.user.get_full_name()}"
```

Run `python manage.py makemigrations users` after adding this.

---

### 1.2 DRF Permission Classes

**File:** `backend/users/permissions.py` (create new file)

```python
from rest_framework.permissions import BasePermission
from family.models import FamilyMember
from users.models import ClinicalRelationship


class IsPatient(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.user_type == 'PATIENT'


class IsFamily(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.user_type == 'FAMILY'


class IsDoctor(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.user_type == 'DOCTOR'


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.user_type == 'ADMIN'


class IsFamilyOrDoctor(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.user_type in ('FAMILY', 'DOCTOR', 'ADMIN')


class CanAccessPatientData(BasePermission):
    """
    Object-level permission. Pass a PatientProfile as the object.
    - PATIENT: only their own profile.
    - FAMILY: only linked patients (active FamilyMember).
    - DOCTOR: only linked patients (active ClinicalRelationship).
    - ADMIN: all patients.
    """
    def has_object_permission(self, request, view, obj):
        # obj is expected to be a PatientProfile
        from patients.models import PatientProfile
        if isinstance(obj, PatientProfile):
            patient = obj
        else:
            patient = getattr(obj, 'patient', None)
        if patient is None:
            return False

        user = request.user
        if user.user_type == 'PATIENT':
            return hasattr(user, 'patient_profile') and user.patient_profile == patient
        if user.user_type == 'FAMILY':
            return FamilyMember.objects.filter(
                user=user, patient=patient, is_active=True
            ).exists()
        if user.user_type == 'DOCTOR':
            return ClinicalRelationship.objects.filter(
                doctor=user, patient=patient, is_active=True
            ).exists()
        if user.user_type == 'ADMIN':
            return True
        return False
```

Apply `CanAccessPatientData` as `permission_classes` on every DRF view that accepts a `patient_id` URL segment. Call `self.check_object_permissions(request, patient)` after fetching the `PatientProfile`.

---

### 1.3 WebSocket Access Control

**File:** `backend/agent/live_consumer.py`

#### Patient-only connect guard

In `GeminiLiveConsumer.connect()`, immediately after the user authentication check (line ~42), add:

```python
if self.user.user_type != 'PATIENT':
    await self.close(code=4003)
    return
patient = await database_sync_to_async(
    PatientProfile.objects.filter(user=self.user).first
)()
if not patient:
    await self.close(code=4004)
    return
self.patient = patient
```

#### Remote viewer WebSocket consumer

**File:** `backend/agent/remote_viewer_consumer.py` (create new file)

This consumer is for FAMILY and DOCTOR accounts. It joins the channel group `patient_{patient_id}_updates` and forwards any events (vitals, activity logs, alerts, messages) pushed to that group.

```python
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from family.models import FamilyMember
from users.models import ClinicalRelationship
from patients.models import PatientProfile


class RemoteViewerConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.user = self.scope.get('user')
        if not self.user or not self.user.is_authenticated:
            await self.close(code=4001)
            return
        if self.user.user_type not in ('FAMILY', 'DOCTOR', 'ADMIN'):
            await self.close(code=4003)
            return

        patient_id = self.scope['url_route']['kwargs']['patient_id']
        authorized = await self._check_access(patient_id)
        if not authorized:
            await self.close(code=4005)
            return

        self.group_name = f'patient_{patient_id}_updates'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    @database_sync_to_async
    def _check_access(self, patient_id):
        try:
            patient = PatientProfile.objects.get(pk=patient_id)
        except PatientProfile.DoesNotExist:
            return False
        if self.user.user_type == 'FAMILY':
            return FamilyMember.objects.filter(
                user=self.user, patient=patient, is_active=True
            ).exists()
        if self.user.user_type == 'DOCTOR':
            return ClinicalRelationship.objects.filter(
                doctor=self.user, patient=patient, is_active=True
            ).exists()
        return self.user.user_type == 'ADMIN'

    # Handlers for each event type pushed to the group
    async def vital_recorded(self, event):
        await self.send_json({'type': 'vital_recorded', 'data': event['data']})

    async def activity_logged(self, event):
        await self.send_json({'type': 'activity_logged', 'data': event['data']})

    async def alert_created(self, event):
        await self.send_json({'type': 'alert_created', 'data': event['data']})

    async def summary_updated(self, event):
        await self.send_json({'type': 'summary_updated', 'data': event['data']})
```

**File:** `backend/carepal/routing.py` — add the new path:

```python
path('ws/remote-viewer/<int:patient_id>/', RemoteViewerConsumer.as_asgi()),
```

#### Live-push from existing tool handlers

In `live_consumer.py`, after every `save_vital_reading` and `_save_activity_log` call, send a push to the remote viewer group:

```python
await self.channel_layer.group_send(
    f'patient_{self.patient.id}_updates',
    {'type': 'vital_recorded', 'data': {...}}
)
```

---

## 2. Medication Adherence via Medication Monitor Agent

### Architecture Decision

Rather than adding more tool calls to the Gemini Live AI session, medication adherence is handled by a **dedicated secondary agent** — the Medication Monitor Agent — that runs asynchronously in the Celery worker pool. 

**Why this is better than giving Live AI more tools:**
- Live AI is a real-time conversational stream; adding DB-write tool calls increases latency and failure surface mid-conversation
- The secondary agent has its own full context window: it can read today's full schedule, all of today's adherence records, and recent medication logs before deciding what to write
- Prevents duplicate marking — if a patient mentions the same medication twice, the agent checks existing adherence records before acting
- Cleanly separates concerns: Live AI captures what was said, the Monitor Agent decides what it means

**Flow:**

```
Patient talks to Gemini Live
        │
        ▼
log_patient_activity(activity_type='MEDICATION') fires
        │
        ▼
PatientActivityLog saved to DB
        │
Django post_save signal (agent/signals.py)
        │
        ▼
Celery task: process_medication_log.delay(log_id)
        │
        ▼
┌─────────────────────────────────────────┐
│       Medication Monitor Agent          │
│       (gemini-2.0-flash, text only)     │
│                                         │
│  Context provided:                      │
│  - The activity log entry (description) │
│  - Patient's full active med schedule   │
│  - Today's adherence records so far     │
│  - Last 3 MEDICATION activity logs      │
│                                         │
│  Tools available:                       │
│  - update_adherence                     │
│  - request_clarification                │
│  - do_nothing                           │
└─────────────────────────────────────────┘
        │
        ▼
DB updated (MedicationAdherence) with source=MONITOR_AGENT
+ audit trail linking back to triggering PatientActivityLog
```

---

### 2.1 Live AI: System Prompt Update Only

The Live AI's only responsibility is to **ask about medications periodically and log what the patient says** using the existing `log_patient_activity` tool with `activity_type='MEDICATION'`. No new tool calls needed on the Live AI side.

**File:** `backend/agent/live_consumer.py`

In the `system_instruction` string, add to the **Rules** section:

```
Medication Check-ins:
- Periodically ask the patient about their medication schedule based on the time of day.
  For example, in the morning ask if they have taken their morning medications.
- When the patient says anything about medications — taken, skipped, unsure, side effects,
  or mentions a medication by name — immediately call log_patient_activity with
  activity_type='MEDICATION'. Capture exactly what they said in the description field.
- Do not attempt to interpret or judge adherence yourself. Just log faithfully.
- Examples of what to log: "Patient said they took Metformin after breakfast",
  "Patient said they haven't taken their evening blood pressure pill yet",
  "Patient mentioned feeling dizzy after taking their medication",
  "Patient said they skipped their noon dose because they forgot".
- Do not ask about medications more than once per scheduled time window
  (morning / afternoon / evening / night).
```

---

### 2.2 Model Change — `confirmation_method` on `MedicationAdherence`

**File:** `backend/medications/models.py`

Check if `MedicationAdherence` already has a `confirmation_method` field. If not, add:

```python
CONFIRMATION_METHOD_CHOICES = [
    ('DEVICE', 'Smart Device'),
    ('MANUAL', 'Manual Entry'),
    ('AI_VERBAL', 'AI Verbal Confirmation'),
    ('MONITOR_AGENT', 'Medication Monitor Agent'),
    ('FAMILY', 'Family Reported'),
]
confirmation_method = models.CharField(
    max_length=20,
    choices=CONFIRMATION_METHOD_CHOICES,
    default='MANUAL',
    blank=True,
)
# Link back to the activity log that triggered this update — audit trail
source_activity_log = models.ForeignKey(
    'agent.PatientActivityLog',
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    related_name='adherence_updates',
    help_text="The activity log entry that caused this adherence record to be written.",
)
```

Run: `python manage.py makemigrations medications`

---

### 2.3 Pending Clarification Queue — Reusable Model

This model is used by the Monitor Agent (and any future agent) to push a follow-up question back into the Live AI's next session. It is **reusable** — any backend process can insert a row, and the Live AI checks for pending items at the start of each session.

**File:** `backend/agent/models.py`

Add alongside existing models:

```python
class PendingQuestion(models.Model):
    """
    A question or prompt queued by a backend agent or process to be
    asked by the Live AI during the patient's next session.

    Reusable: any backend agent inserts a row here. The Live AI
    reads and clears pending questions at session start.
    """
    SOURCE_CHOICES = [
        ('MEDICATION_AGENT', 'Medication Monitor Agent'),
        ('SYSTEM', 'System'),
        ('DOCTOR', 'Doctor'),
        ('FAMILY', 'Family Member'),
    ]

    patient = models.ForeignKey(
        'patients.PatientProfile',
        on_delete=models.CASCADE,
        related_name='pending_questions',
    )
    question = models.TextField(
        help_text="The exact question or prompt to inject into the Live AI session."
    )
    context = models.TextField(
        blank=True,
        help_text="Internal context for why this question is being asked. "
                  "Not shown to the patient — used to help the AI frame the question naturally."
    )
    source = models.CharField(max_length=30, choices=SOURCE_CHOICES, default='SYSTEM')
    source_object_type = models.CharField(
        max_length=50, blank=True,
        help_text="Optional: model name of the object that triggered this question."
    )
    source_object_id = models.IntegerField(
        null=True, blank=True,
        help_text="Optional: PK of the triggering object for audit trail."
    )
    priority = models.IntegerField(
        default=5,
        help_text="1 = highest priority (ask first), 10 = lowest. "
                  "Live AI asks pending questions in priority order."
    )
    asked = models.BooleanField(default=False)
    asked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(
        null=True, blank=True,
        help_text="If the question is still pending after this time, discard it."
    )

    class Meta:
        db_table = 'pending_questions'
        ordering = ['priority', 'created_at']

    def __str__(self):
        return f"[{self.source}] {self.question[:60]}"
```

Run: `python manage.py makemigrations agent`

---

### 2.4 Live AI: Load Pending Questions at Session Start

**File:** `backend/agent/live_consumer.py`

After the patient is authenticated and `self.patient` is set in `connect()`, fetch any pending questions and inject them into the session's system context.

```python
@database_sync_to_async
def _get_pending_questions(self):
    from django.utils import timezone
    from .models import PendingQuestion
    now = timezone.now()
    return list(
        PendingQuestion.objects.filter(
            patient=self.patient,
            asked=False,
        ).filter(
            models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=now)
        ).order_by('priority', 'created_at')
    )

@database_sync_to_async
def _mark_questions_asked(self, question_ids):
    from django.utils import timezone
    from .models import PendingQuestion
    PendingQuestion.objects.filter(id__in=question_ids).update(
        asked=True,
        asked_at=timezone.now(),
    )
```

In `run_gemini_session()`, after building `system_instruction`, append pending questions:

```python
pending = await self._get_pending_questions()
if pending:
    question_block = "\n\nPENDING FOLLOW-UP QUESTIONS (ask these naturally early in the session):\n"
    for pq in pending:
        question_block += f"- {pq.question}"
        if pq.context:
            question_block += f"  [Context for you only: {pq.context}]"
        question_block += "\n"
    system_instruction += question_block
    await self._mark_questions_asked([pq.id for pq in pending])
```

---

### 2.5 Django Signal — Trigger Celery Task on MEDICATION Log

**File:** `backend/agent/signals.py` (create new file)

```python
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import PatientActivityLog


@receiver(post_save, sender=PatientActivityLog)
def on_activity_log_saved(sender, instance, created, **kwargs):
    if created and instance.activity_type == 'MEDICATION':
        from .tasks import process_medication_log
        process_medication_log.delay(instance.id)
```

**File:** `backend/agent/apps.py` — register the signal:

```python
class AgentConfig(AppConfig):
    name = 'agent'

    def ready(self):
        import agent.signals  # noqa
```

---

### 2.6 Celery Task

**File:** `backend/agent/tasks.py` (add to existing tasks or create new file)

```python
@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def process_medication_log(self, activity_log_id: int):
    """
    Triggered whenever a MEDICATION activity log is saved.
    Calls the Medication Monitor Agent to interpret the log
    and update adherence records if appropriate.
    """
    try:
        from .models import PatientActivityLog
        log = PatientActivityLog.objects.select_related(
            'patient__user'
        ).get(id=activity_log_id)
        
        from .medication_monitor_agent import MedicationMonitorAgent
        agent = MedicationMonitorAgent()
        agent.process(log)

    except PatientActivityLog.DoesNotExist:
        logger.warning(f"process_medication_log: log {activity_log_id} not found")
    except Exception as exc:
        logger.error(f"process_medication_log failed: {exc}")
        raise self.retry(exc=exc)
```

---

### 2.7 Medication Monitor Agent

**File:** `backend/agent/medication_monitor_agent.py` (new file)

This is a standard (non-streaming) Gemini text call. It receives full context, reasons about it, and calls one of three tools.

#### Context builder

```python
def _build_context(self, log: PatientActivityLog) -> str:
    from medications.models import Medication, MedicationAdherence, MedicationSchedule
    from datetime import date

    patient = log.patient
    today = date.today()

    # 1. Active medications + their schedules
    meds = Medication.objects.filter(
        patient=patient, status='ACTIVE'
    ).prefetch_related('schedules')

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

    # 2. Today's adherence records already written
    adherence_today = MedicationAdherence.objects.filter(
        medication__patient=patient,
        scheduled_date=today,
    ).select_related('medication')

    adherence_lines = []
    for a in adherence_today:
        adherence_lines.append(
            f"  - {a.medication.medication_name}: {a.status} "
            f"(recorded at {a.actual_datetime}, method: {a.confirmation_method})"
        )

    # 3. Last 3 MEDICATION activity logs (excluding current)
    recent_logs = PatientActivityLog.objects.filter(
        patient=patient,
        activity_type='MEDICATION',
    ).exclude(id=log.id).order_by('-observed_at')[:3]

    recent_lines = [
        f"  - [{r.observed_at.strftime('%H:%M')}] {r.description}"
        for r in recent_logs
    ]

    return f"""
PATIENT: {patient.user.get_full_name()}
DATE: {today}
TIME OF LOG: {log.observed_at.strftime('%Y-%m-%d %H:%M')}

WHAT THE PATIENT SAID (activity log description):
"{log.description}"

ACTIVE MEDICATIONS ON SCHEDULE TODAY:
{chr(10).join(med_lines) or '  (none)'}

TODAY'S ADHERENCE RECORDS ALREADY WRITTEN:
{chr(10).join(adherence_lines) or '  (none yet)'}

RECENT MEDICATION ACTIVITY LOGS (last 3, excluding this one):
{chr(10).join(recent_lines) or '  (none)'}
"""
```

#### Tool definitions

```python
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
            "to update adherence AND clarification is not warranted — for example if the "
            "patient is simply discussing medications in general without referring to a "
            "specific dose event, or if the log is already fully accounted for in today's "
            "adherence records."
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
```

#### Agent system prompt

```python
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
```

#### Full agent class

```python
import logging
from google import genai
from google.genai import types as gtypes
from django.conf import settings

logger = logging.getLogger(__name__)


class MedicationMonitorAgent:

    def __init__(self):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)

    def process(self, log) -> None:
        context = self._build_context(log)
        response = self.client.models.generate_content(
            model='gemini-2.0-flash',
            contents=context,
            config=gtypes.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                tools=[gtypes.Tool(function_declarations=[
                    gtypes.FunctionDeclaration(**t) for t in TOOLS
                ])],
                tool_config=gtypes.ToolConfig(
                    function_calling_config=gtypes.FunctionCallingConfig(
                        mode='ANY',  # Must call a tool — no plain text responses
                    )
                ),
                temperature=0.1,  # Low temperature — this is a classification task
            ),
        )

        for part in response.candidates[0].content.parts:
            if part.function_call:
                self._dispatch(part.function_call, log)
                break

    def _dispatch(self, fc, log) -> None:
        args = dict(fc.args)
        if fc.name == 'update_adherence':
            self._update_adherence(
                log=log,
                medication_name=args['medication_name'],
                status=args['status'],
                notes=args.get('notes', ''),
                confidence=args.get('confidence', 1.0),
            )
        elif fc.name == 'request_clarification':
            self._queue_clarification(
                log=log,
                question=args['question'],
                context=args.get('context', ''),
                priority=args.get('priority', 5),
            )
        elif fc.name == 'do_nothing':
            logger.info(
                f"[MedAgent] do_nothing for log {log.id}: {args.get('reason', '')}"
            )

    def _update_adherence(
        self, log, medication_name: str, status: str,
        notes: str, confidence: float
    ) -> None:
        from medications.models import Medication, MedicationAdherence, MedicationSchedule
        from django.utils import timezone
        from datetime import date

        if confidence < 0.6:
            logger.warning(
                f"[MedAgent] Skipping update for log {log.id} — "
                f"confidence {confidence} below threshold"
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
            logger.warning(
                f"[MedAgent] Medication not found: '{medication_name}' "
                f"for patient {patient.id}"
            )
            return

        # Duplicate guard — don't overwrite an already-decided record
        existing = MedicationAdherence.objects.filter(
            medication=med,
            scheduled_date=today,
            status__in=['TAKEN', 'SKIPPED'],
        ).first()
        if existing:
            logger.info(
                f"[MedAgent] Skipping — adherence already recorded as "
                f"{existing.status} for {med.medication_name} today"
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
            f"{med.medication_name} → {status} "
            f"(confidence={confidence}, log={log.id})"
        )

    def _queue_clarification(
        self, log, question: str, context: str, priority: int
    ) -> None:
        from .models import PendingQuestion
        from django.utils import timezone
        from datetime import timedelta

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
        logger.info(
            f"[MedAgent] Queued clarification for log {log.id}: '{question}'"
        )

    # _build_context defined above (insert here)
```

---

### 2.8 Migrations Checklist

Run in order:

```bash
docker compose exec backend python manage.py makemigrations medications --name="add_confirmation_method_source_log"
docker compose exec backend python manage.py makemigrations agent --name="add_pending_question_model"
docker compose exec backend python manage.py migrate
```

---

### 2.9 Summary of Files Changed / Created

| File | Change |
|---|---|
| `backend/medications/models.py` | Add `confirmation_method`, `source_activity_log` to `MedicationAdherence` |
| `backend/agent/models.py` | Add `PendingQuestion` model |
| `backend/agent/signals.py` | New — `post_save` signal on `PatientActivityLog` |
| `backend/agent/apps.py` | Register signals in `ready()` |
| `backend/agent/tasks.py` | Add `process_medication_log` Celery task |
| `backend/agent/medication_monitor_agent.py` | New — full agent class |
| `backend/agent/live_consumer.py` | System prompt update + pending question injection at session start |

---

## 3. Nutrition Logging (Structured)

### Current State

`log_patient_activity` with `activity_type=MEAL` is called, creating a `PatientActivityLog` entry. There is no dedicated `NutritionLog` model, no calorie tracking, no threshold alerts.

---

### 3.1 PatientProfile Field Additions

**File:** `backend/patients/models.py` — add to `PatientProfile`:

```python
daily_calorie_target = models.IntegerField(
    null=True, blank=True,
    help_text="Target daily caloric intake in kcal. Null means no tracking."
)
nutrition_alert_threshold_percent = models.IntegerField(
    default=70,
    help_text="Alert when daily intake falls below this % of target (e.g. 70 = alert if <70% of target reached)."
)
```

Run `python manage.py makemigrations patients`.

---

### 3.2 New Model — `NutritionLog`

**File:** `backend/agent/models.py` (alongside `PatientActivityLog`)

```python
class NutritionLog(models.Model):
    MEAL_TYPE_CHOICES = [
        ('BREAKFAST', 'Breakfast'),
        ('LUNCH', 'Lunch'),
        ('DINNER', 'Dinner'),
        ('SNACK', 'Snack'),
        ('OTHER', 'Other'),
    ]
    SOURCE_CHOICES = [
        ('AI_INFERRED', 'AI Inferred'),
        ('MANUAL', 'Manual Entry'),
    ]

    patient = models.ForeignKey(
        PatientProfile, on_delete=models.CASCADE, related_name='nutrition_logs'
    )
    logged_at = models.DateTimeField(auto_now_add=True)
    meal_time = models.DateTimeField(
        help_text="When the meal was consumed (may differ from logged_at)"
    )
    meal_type = models.CharField(max_length=15, choices=MEAL_TYPE_CHOICES, default='OTHER')
    description = models.TextField()
    estimated_kcal = models.IntegerField(
        null=True, blank=True,
        help_text="AI-estimated or manually entered kilocalories"
    )
    items = models.JSONField(
        default=list, blank=True,
        help_text="List of food items: [{'name': 'rice', 'qty': '1 cup', 'kcal': 200}]"
    )
    below_threshold = models.BooleanField(default=False)
    source = models.CharField(max_length=15, choices=SOURCE_CHOICES, default='AI_INFERRED')
    activity_log = models.OneToOneField(
        PatientActivityLog,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='nutrition_log'
    )

    class Meta:
        db_table = 'nutrition_logs'
        ordering = ['-meal_time']
        indexes = [
            models.Index(fields=['patient', '-meal_time']),
        ]

    def __str__(self):
        return f"{self.patient.user.get_full_name()} | {self.meal_type} | {self.meal_time:%Y-%m-%d %H:%M}"
```

---

### 3.3 Auto-Create NutritionLog from `_save_activity_log`

**File:** `backend/agent/live_consumer.py`

At the end of `_save_activity_log()`, after `log_entry.save()`, add:

```python
# Auto-create NutritionLog for MEAL entries
if params.get('activity_type') == 'MEAL':
    details = params.get('details', {}) or {}
    NutritionLog.objects.create(
        patient=patient,
        meal_time=observed_at,
        meal_type=details.get('meal_type', 'OTHER').upper(),
        description=params.get('description', ''),
        estimated_kcal=details.get('estimated_kcal'),
        items=details.get('meal_items', []),
        source='AI_INFERRED',
        activity_log=log_entry,
    )
```

Import `NutritionLog` at the top of the method's import block.

---

### 3.4 Updated Tool Schema

**File:** `backend/agent/live_consumer.py`

In the `log_patient_activity` `FunctionDeclaration`, update the `details` field description:

```
MEAL → {
  meal_type: "BREAKFAST|LUNCH|DINNER|SNACK|OTHER",
  estimated_kcal: <integer — best estimate total calories>,
  meal_items: [{"name": "...", "qty": "..."}],
  appetite: "GOOD|POOR|NORMAL"
}
```

---

### 3.5 Celery Task — `check_daily_nutrition_threshold`

**File:** `backend/agent/tasks.py` (create or add to existing)

```python
from celery import shared_task
from django.utils import timezone
from datetime import timedelta

@shared_task
def check_daily_nutrition_threshold():
    """
    Runs at 21:00 daily (schedule in celery beat).
    For each patient with a daily_calorie_target, sum today's NutritionLog kcal.
    If below threshold for N consecutive days, create an Alert.
    """
    from patients.models import PatientProfile
    from agent.models import NutritionLog
    from alerts.models import Alert, AlertType

    today = timezone.now().date()
    CONSECUTIVE_DAYS_THRESHOLD = 2

    for patient in PatientProfile.objects.filter(
        daily_calorie_target__isnull=False, is_active=True
    ):
        target = patient.daily_calorie_target
        threshold_kcal = int(target * patient.nutrition_alert_threshold_percent / 100)

        today_logs = NutritionLog.objects.filter(
            patient=patient,
            meal_time__date=today,
            estimated_kcal__isnull=False
        )
        today_kcal = sum(l.estimated_kcal for l in today_logs)

        # Mark below_threshold
        today_logs.update(below_threshold=(today_kcal < threshold_kcal))

        # Check consecutive low days
        if today_kcal < threshold_kcal:
            low_days = 0
            for i in range(CONSECUTIVE_DAYS_THRESHOLD):
                day = today - timedelta(days=i)
                day_kcal = (
                    NutritionLog.objects.filter(
                        patient=patient,
                        meal_time__date=day,
                        estimated_kcal__isnull=False
                    ).aggregate(total=models.Sum('estimated_kcal'))['total'] or 0
                )
                if day_kcal < threshold_kcal:
                    low_days += 1
            if low_days >= CONSECUTIVE_DAYS_THRESHOLD:
                alert_type, _ = AlertType.objects.get_or_create(
                    code='NUTRITION_LOW',
                    defaults={
                        'name': 'Low Nutrition Intake',
                        'category': 'HEALTH_TREND',
                        'default_severity': 'WARNING',
                        'message_template': 'Patient {patient_name} has been below their nutrition target for {days} consecutive days.',
                    }
                )
                Alert.objects.create(
                    alert_type=alert_type,
                    patient=patient,
                    severity='WARNING',
                    title='Low Nutrition Alert',
                    message=f'Caloric intake below {patient.nutrition_alert_threshold_percent}% of target for {low_days} consecutive days.',
                    context_data={'today_kcal': today_kcal, 'target': target, 'threshold_kcal': threshold_kcal},
                )
```

**Celery Beat schedule** (in `backend/carepal/settings.py` or `celery.py`):

```python
'check-daily-nutrition': {
    'task': 'agent.tasks.check_daily_nutrition_threshold',
    'schedule': crontab(hour=21, minute=0),
},
```

---

## 4. Mood Logging (Structured)

### Current State

`log_patient_activity` with `activity_type=MOOD` creates a `PatientActivityLog`. No dedicated `MoodLog`, no baseline, no occurrence counting.

---

### 4.1 PatientProfile Field Addition

**File:** `backend/patients/models.py`

```python
mood_baseline_score = models.IntegerField(
    default=7,
    help_text="Baseline mood score (1-10). Mood below this triggers a flag."
)
```

---

### 4.2 New Model — `MoodLog`

**File:** `backend/agent/models.py`

```python
class MoodLog(models.Model):
    MOOD_LABEL_CHOICES = [
        ('POSITIVE', 'Positive'),
        ('NEUTRAL', 'Neutral'),
        ('LOW', 'Low'),
        ('DISTRESSED', 'Distressed'),
    ]
    SOURCE_CHOICES = [
        ('AI_INFERRED', 'AI Inferred'),
        ('MANUAL', 'Manual Entry'),
    ]

    patient = models.ForeignKey(
        PatientProfile, on_delete=models.CASCADE, related_name='mood_logs'
    )
    logged_at = models.DateTimeField(auto_now_add=True)
    observed_at = models.DateTimeField()
    mood_score = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="1 (worst) to 10 (best)"
    )
    mood_label = models.CharField(max_length=15, choices=MOOD_LABEL_CHOICES, default='NEUTRAL')
    description = models.TextField()
    triggers = models.JSONField(
        default=list, blank=True,
        help_text="Identified triggers e.g. ['pain', 'loneliness', 'missed_call']"
    )
    is_below_baseline = models.BooleanField(default=False)
    occurrence_this_week = models.IntegerField(
        default=0,
        help_text="Count of below-baseline entries this calendar week (computed on save)"
    )
    source = models.CharField(max_length=15, choices=SOURCE_CHOICES, default='AI_INFERRED')
    activity_log = models.OneToOneField(
        PatientActivityLog,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='mood_log'
    )

    class Meta:
        db_table = 'mood_logs'
        ordering = ['-observed_at']
        indexes = [
            models.Index(fields=['patient', '-observed_at']),
            models.Index(fields=['is_below_baseline', '-observed_at']),
        ]

    def __str__(self):
        return f"{self.patient.user.get_full_name()} | {self.mood_label} ({self.mood_score}) | {self.observed_at:%Y-%m-%d %H:%M}"
```

---

### 4.3 Auto-Create MoodLog from `_save_activity_log`

**File:** `backend/agent/live_consumer.py`

After saving the `PatientActivityLog`, for MOOD entries:

```python
if params.get('activity_type') == 'MOOD':
    from datetime import timedelta
    details = params.get('details', {}) or {}
    mood_score = details.get('mood_score')
    mood_label_raw = details.get('mood_label', 'NEUTRAL').upper()
    valid_labels = {'POSITIVE', 'NEUTRAL', 'LOW', 'DISTRESSED'}
    mood_label = mood_label_raw if mood_label_raw in valid_labels else 'NEUTRAL'

    baseline = patient.mood_baseline_score
    is_below = (mood_score is not None and mood_score < baseline) or mood_label in ('LOW', 'DISTRESSED')

    # Count below-baseline this week
    week_start = observed_at - timedelta(days=observed_at.weekday())
    week_count = MoodLog.objects.filter(
        patient=patient,
        observed_at__gte=week_start,
        is_below_baseline=True
    ).count()
    if is_below:
        week_count += 1  # Include this one

    mood_entry = MoodLog.objects.create(
        patient=patient,
        observed_at=observed_at,
        mood_score=mood_score,
        mood_label=mood_label,
        description=params.get('description', ''),
        triggers=details.get('triggers', []),
        is_below_baseline=is_below,
        occurrence_this_week=week_count,
        source='AI_INFERRED',
        activity_log=log_entry,
    )

    # Auto-flag if 3+ low moods this week
    if is_below and week_count >= 3:
        from alerts.models import Alert, AlertType
        alert_type, _ = AlertType.objects.get_or_create(
            code='MOOD_CONCERN',
            defaults={
                'name': 'Mood Concern',
                'category': 'HEALTH_TREND',
                'default_severity': 'WARNING',
                'message_template': 'Patient {patient_name} has reported low mood {count} times this week.',
            }
        )
        Alert.objects.get_or_create(
            alert_type=alert_type,
            patient=patient,
            status='PENDING',
            context_data__contains={'week_occurrences': week_count},
            defaults={
                'severity': 'WARNING',
                'title': 'Repeated Low Mood This Week',
                'message': f'Patient has logged low/distressed mood {week_count} times this week.',
                'context_data': {'week_occurrences': week_count, 'mood_label': mood_label},
            }
        )
```

---

### 4.4 Updated Tool Schema

In `log_patient_activity` `FunctionDeclaration`, update `details` description for MOOD:

```
MOOD → {
  mood_score: <integer 1-10, where 1=severely distressed, 10=very happy>,
  mood_label: "POSITIVE|NEUTRAL|LOW|DISTRESSED",
  energy_level: "HIGH|NORMAL|LOW",
  triggers: ["pain", "loneliness", "boredom"]  — list any mentioned triggers
}
```

---

## 5. Escalation Timeline

### What Is an Escalation Timeline

An escalation timeline is a chronological record of a multi-signal health incident. It begins when two or more independently concerning signals (e.g. abnormally high blood pressure + distressed mood + late-night unusual behavior) co-occur within a short window. It then tracks every response step — alert sent, family notified, nurse called, home visit arranged — through to resolution. The timeline answers the question: *"What happened, who was notified when, how did they respond, and what was the final outcome?"*

---

### 5.1 New Models

**File:** `backend/alerts/models.py`

```python
class EscalationEvent(models.Model):
    TRIGGER_TYPE_CHOICES = [
        ('MULTI_SIGNAL', 'Multiple Concurrent Signals'),
        ('VITAL_ANOMALY', 'Vital Sign Anomaly'),
        ('FALL', 'Fall Detected'),
        ('MEDICATION_MISSED', 'Critical Medication Missed'),
        ('MANUAL', 'Manually Triggered'),
    ]
    SEVERITY_CHOICES = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('CRITICAL', 'Critical'),
    ]
    STATUS_CHOICES = [
        ('OPEN', 'Open'),
        ('IN_PROGRESS', 'In Progress'),
        ('RESOLVED', 'Resolved'),
    ]

    patient = models.ForeignKey(
        PatientProfile, on_delete=models.CASCADE, related_name='escalation_events'
    )
    triggered_at = models.DateTimeField(auto_now_add=True)
    trigger_type = models.CharField(max_length=20, choices=TRIGGER_TYPE_CHOICES)
    trigger_description = models.TextField()
    signals = models.JSONField(
        default=list,
        help_text="Contributing signals: [{'type': 'MOOD', 'detail': 'DISTRESSED x3'}, {'type': 'VITAL', 'detail': 'BP 165/105'}]"
    )
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='MEDIUM')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='OPEN')
    outcome_note = models.TextField(blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'escalation_events'
        ordering = ['-triggered_at']

    def __str__(self):
        return f"Escalation [{self.severity}] {self.patient.user.get_full_name()} @ {self.triggered_at:%Y-%m-%d %H:%M}"


class EscalationStep(models.Model):
    STEP_TYPE_CHOICES = [
        ('ALERT_SENT', 'Alert Sent'),
        ('NOTIFIED_FAMILY', 'Family Notified'),
        ('NOTIFIED_DOCTOR', 'Doctor Notified'),
        ('NURSE_RESPONDED', 'Nurse Responded'),
        ('HOME_VISIT_ARRANGED', 'Home Visit Arranged'),
        ('RESOLVED', 'Resolved'),
    ]

    event = models.ForeignKey(
        EscalationEvent, on_delete=models.CASCADE, related_name='steps'
    )
    step_type = models.CharField(max_length=25, choices=STEP_TYPE_CHOICES)
    occurred_at = models.DateTimeField(auto_now_add=True)
    actor = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='escalation_steps'
    )
    note = models.TextField(blank=True)

    class Meta:
        db_table = 'escalation_steps'
        ordering = ['occurred_at']

    def __str__(self):
        return f"{self.event} → {self.step_type} @ {self.occurred_at:%H:%M}"
```

---

### 5.2 Signal Handler / Celery Task — `detect_multi_signal_escalation`

**File:** `backend/alerts/tasks.py`

```python
from celery import shared_task

@shared_task
def detect_multi_signal_escalation(patient_id: int):
    """
    Called after any PatientActivityLog, VitalReading, or MoodLog save.
    Checks for 2+ notable/anomalous signals in the last 2 hours.
    If found, creates an EscalationEvent.
    """
    from django.utils import timezone
    from datetime import timedelta
    from patients.models import PatientProfile
    from agent.models import PatientActivityLog, MoodLog
    from vitals.models import VitalReading
    from alerts.models import EscalationEvent, EscalationStep

    window_start = timezone.now() - timedelta(hours=2)
    try:
        patient = PatientProfile.objects.get(pk=patient_id)
    except PatientProfile.DoesNotExist:
        return

    signals = []

    # Notable activity logs
    for log in PatientActivityLog.objects.filter(
        patient=patient, observed_at__gte=window_start, is_notable=True
    ):
        signals.append({'type': log.activity_type, 'detail': log.notable_reason or log.description, 'id': log.pk})

    # Below-baseline moods
    for mood in MoodLog.objects.filter(
        patient=patient, observed_at__gte=window_start, is_below_baseline=True
    ):
        signals.append({'type': 'MOOD', 'detail': f'{mood.mood_label} (score {mood.mood_score})', 'id': mood.pk})

    # Anomalous vitals — readings flagged is_anomalous if that field exists, else skip
    for reading in VitalReading.objects.filter(
        patient=patient, measured_at__gte=window_start
    ).select_related('vital_type'):
        if getattr(reading, 'is_anomalous', False):
            signals.append({'type': 'VITAL', 'detail': f'{reading.vital_type.name}: {reading.get_display_value()}', 'id': reading.pk})

    if len(signals) < 2:
        return  # Not enough concurrent signals

    # Avoid duplicate events within the same window
    already_open = EscalationEvent.objects.filter(
        patient=patient,
        triggered_at__gte=window_start,
        status__in=['OPEN', 'IN_PROGRESS']
    ).exists()
    if already_open:
        return

    # Determine severity
    severity = 'HIGH' if len(signals) >= 4 else 'MEDIUM'

    event = EscalationEvent.objects.create(
        patient=patient,
        trigger_type='MULTI_SIGNAL',
        trigger_description=f'{len(signals)} concurrent signals detected within 2-hour window.',
        signals=signals,
        severity=severity,
    )
    EscalationStep.objects.create(
        event=event,
        step_type='ALERT_SENT',
        note='System automatically detected multi-signal escalation.',
    )

    # Trigger push notifications (see Section 10)
    from alerts.services import send_push_notification
    from family.models import FamilyMember
    from users.models import ClinicalRelationship

    family_user_ids = list(
        FamilyMember.objects.filter(patient=patient, is_active=True)
        .values_list('user_id', flat=True)
    )
    doctor_user_ids = list(
        ClinicalRelationship.objects.filter(patient=patient, is_active=True)
        .values_list('doctor_id', flat=True)
    )
    all_recipients = list(set(family_user_ids + doctor_user_ids))
    send_push_notification.delay(
        user_ids=all_recipients,
        title=f"Health Alert — {patient.user.get_full_name()}",
        body=f"{len(signals)} concerning signals detected in the last 2 hours.",
        data={'escalation_event_id': event.pk, 'patient_id': patient_id},
    )
```

**Trigger the task** by adding Django signals in `backend/agent/signals.py`:

```python
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender='agent.PatientActivityLog')
@receiver(post_save, sender='agent.MoodLog')
@receiver(post_save, sender='vitals.VitalReading')
def trigger_escalation_check(sender, instance, created, **kwargs):
    if created:
        from alerts.tasks import detect_multi_signal_escalation
        patient_id = instance.patient_id
        detect_multi_signal_escalation.apply_async(args=[patient_id], countdown=5)
```

Register in `backend/agent/apps.py`:

```python
def ready(self):
    import agent.signals  # noqa
```

---

### 5.3 API Endpoints

**File:** `backend/alerts/views.py` — add:

```python
# GET /api/patients/{patient_id}/escalations/
# GET /api/patients/{patient_id}/escalations/{event_id}/steps/
```

Use `CanAccessPatientData` permission. Serializers: `EscalationEventSerializer` (nested with `EscalationStepSerializer`).

**File:** `backend/alerts/urls.py`:

```python
path('patients/<int:patient_id>/escalations/', EscalationEventListView.as_view()),
path('patients/<int:patient_id>/escalations/<int:event_id>/steps/', EscalationStepListView.as_view()),
```

---

## 6. Patient Question Log & Answer Notification

### Current State

No `PatientQuestion` model exists anywhere. Questions raised during AI conversation are untracked.

---

### 6.1 New Model — `PatientQuestion`

**File:** `backend/agent/models.py`

```python
class PatientQuestion(models.Model):
    STATUS_CHOICES = [
        ('UNANSWERED', 'Unanswered'),
        ('ANSWERED', 'Answered'),
        ('DISMISSED', 'Dismissed'),
    ]

    patient = models.ForeignKey(
        PatientProfile, on_delete=models.CASCADE, related_name='patient_questions'
    )
    agent_session = models.ForeignKey(
        AgentSession, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='patient_questions'
    )
    asked_at = models.DateTimeField(auto_now_add=True)
    question_text = models.TextField()
    context_snippet = models.TextField(
        blank=True,
        help_text="Surrounding 2-3 turns of conversation for context"
    )
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='UNANSWERED')
    answered_at = models.DateTimeField(null=True, blank=True)
    answered_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='answered_questions'
    )
    answer_text = models.TextField(blank=True)
    notify_ai_on_answer = models.BooleanField(
        default=True,
        help_text="If True, push answer back to active AI session"
    )

    class Meta:
        db_table = 'patient_questions'
        ordering = ['-asked_at']

    def __str__(self):
        return f"Q [{self.status}]: {self.question_text[:60]} — {self.patient.user.get_full_name()}"
```

---

### 6.2 Tool Declaration — `log_patient_question`

**File:** `backend/agent/live_consumer.py`

Add to the tools list:

```python
types.FunctionDeclaration(
    name="log_patient_question",
    description=(
        "Log a medical question the patient has asked that you cannot definitively answer "
        "from your general knowledge — for example, questions about their specific medication "
        "side effects, unexplained symptoms, dosage adjustments, or care instructions that "
        "require their doctor's input. Do NOT use for general health facts you can answer yourself."
    ),
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "question_text": types.Schema(
                type="STRING",
                description="The patient's question, verbatim or closely paraphrased."
            ),
            "context": types.Schema(
                type="STRING",
                description="2-3 sentences of surrounding conversation for context."
            ),
        },
        required=["question_text"]
    )
),
```

---

### 6.3 Handler Method

**File:** `backend/agent/live_consumer.py`

```python
async def handle_log_patient_question(self, args: dict, fc_id):
    result = await self._save_patient_question(
        args.get('question_text', ''),
        args.get('context', '')
    )
    if self.session:
        await self.session.send(
            types.FunctionResponse(id=fc_id, name="log_patient_question", response=result)
        )

@database_sync_to_async
def _save_patient_question(self, question_text: str, context: str) -> dict:
    from agent.models import PatientQuestion
    try:
        patient = PatientProfile.objects.filter(user=self.user).first()
        if not patient:
            return {"success": False, "error": "No patient profile"}

        question = PatientQuestion.objects.create(
            patient=patient,
            agent_session=getattr(self, 'db_session', None),
            question_text=question_text,
            context_snippet=context,
        )

        # Push notification to doctors and family (async, see Section 10)
        from alerts.services import send_push_notification
        from family.models import FamilyMember
        from users.models import ClinicalRelationship

        family_ids = list(FamilyMember.objects.filter(patient=patient, is_active=True).values_list('user_id', flat=True))
        doctor_ids = list(ClinicalRelationship.objects.filter(patient=patient, is_active=True).values_list('doctor_id', flat=True))
        send_push_notification.delay(
            user_ids=list(set(family_ids + doctor_ids)),
            title=f"{patient.user.get_full_name()} has a question",
            body=question_text[:120],
            data={'question_id': question.pk, 'patient_id': patient.pk},
        )
        return {"success": True, "question_id": question.pk}
    except Exception as e:
        logger.error(f"Error saving patient question: {e}")
        return {"success": False, "error": str(e)}
```

In the tool dispatch loop, add:

```python
elif fc.name == "log_patient_question":
    asyncio.create_task(self.handle_log_patient_question(fc_args, fc_id))
```

---

### 6.4 Answer API Endpoint

**File:** `backend/agent/views.py`

```python
# POST /api/questions/{id}/answer/
class AnswerPatientQuestionView(APIView):
    permission_classes = [IsAuthenticated, IsFamilyOrDoctor]

    def post(self, request, pk):
        question = get_object_or_404(PatientQuestion, pk=pk)
        self.check_object_permissions(request, question.patient)

        answer_text = request.data.get('answer_text', '').strip()
        if not answer_text:
            return Response({'error': 'answer_text required'}, status=400)

        question.status = 'ANSWERED'
        question.answer_text = answer_text
        question.answered_by = request.user
        question.answered_at = timezone.now()
        question.save()

        # Deliver to live AI session if active
        if question.notify_ai_on_answer:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            channel_layer = get_channel_layer()
            group = f'patient_{question.patient_id}_agent'
            async_to_sync(channel_layer.group_send)(group, {
                'type': 'question.answered',
                'question_id': question.pk,
                'question_text': question.question_text,
                'answer_text': answer_text,
                'answered_by': request.user.get_full_name(),
            })

        return Response({'status': 'answered'})
```

---

### 6.5 Incoming Answer Handling in `live_consumer.py`

There are three distinct cases to handle: the session is active right now, the session is temporarily disconnected, or the patient has not started a session yet. Each is handled differently.

---

#### Case 1 — Session is active: real-time injection

The Gemini Live API session is a persistent bidirectional stream. Text can be sent into it at any point mid-conversation, not just as a reply to audio. `live_consumer.py` already has a `sender_loop` that reads from `self.input_queue` and calls `session.send()`. Injection works by pushing a text item into that queue from outside the consumer via the Django Channels channel layer.

**Step 1 — Join the agent channel group on connect** (after patient is confirmed):

```python
self.agent_group = f'patient_{self.patient.id}_agent'
await self.channel_layer.group_add(self.agent_group, self.channel_name)
```

Add the corresponding `group_discard` on disconnect.

**Step 2 — Add the channel message handler:**

```python
async def question_answered(self, event):
    """
    Triggered by the channel layer when a doctor/family member answers a patient question.
    Injects the answer into the running Gemini session via the sender queue,
    then marks the question as delivered.
    """
    if not self.session:
        # Session is gone — do nothing here; the pending-delivery path (Case 2/3) will handle it
        return

    inject_text = (
        f"[System: A care team answer has just arrived for a question you logged.] "
        f"The patient originally asked: \"{event['question_text']}\". "
        f"{event['answered_by']} has answered: \"{event['answer_text']}\". "
        f"Please relay this answer to the patient naturally and warmly in the ongoing conversation."
    )
    # Push into sender_loop queue — same path as all other outgoing text
    await self.input_queue.put({"text": inject_text})

    # Mark delivered
    await self._mark_question_delivered(event['question_id'])

@database_sync_to_async
def _mark_question_delivered(self, question_id: int):
    from agent.models import PatientQuestion
    PatientQuestion.objects.filter(pk=question_id).update(
        delivered_to_ai=True,
        delivered_to_ai_at=timezone.now()
    )
```

The answer answer endpoint (`AnswerPatientQuestionView`) does **not** set `delivered_to_ai=True` itself — it only stores the answer and fires the channel layer message. Marking delivered happens only when the consumer confirms it received and queued the text.

---

#### Case 2 — Session is temporarily offline: Celery polling recovery

If the channel layer `group_send` fires but no consumer is listening (patient's device disconnected briefly), the message is lost. A lightweight Celery periodic task covers this:

**File:** `backend/agent/tasks.py`

```python
@shared_task
def deliver_pending_question_answers():
    """
    Runs every 60 seconds via Celery Beat.
    For each answered question not yet delivered to the AI,
    check if the patient's agent session is currently active.
    If active, push via channel layer — the consumer will pick it up.
    """
    from agent.models import PatientQuestion, AgentSession
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync

    channel_layer = get_channel_layer()
    pending = PatientQuestion.objects.filter(
        status='ANSWERED',
        notify_ai_on_answer=True,
        delivered_to_ai=False,
    ).select_related('patient', 'answered_by')

    for question in pending:
        # Only attempt if there is an active session for this patient
        is_active = AgentSession.objects.filter(
            patient=question.patient, status='ACTIVE'
        ).exists()
        if not is_active:
            continue

        async_to_sync(channel_layer.group_send)(
            f'patient_{question.patient_id}_agent',
            {
                'type': 'question.answered',
                'question_id': question.pk,
                'question_text': question.question_text,
                'answer_text': question.answer_text,
                'answered_by': question.answered_by.get_full_name() if question.answered_by else 'Care team',
            }
        )
```

Add to Celery Beat schedule:

```python
'deliver-pending-question-answers': {
    'task': 'agent.tasks.deliver_pending_question_answers',
    'schedule': 60.0,  # every 60 seconds
},
```

---

#### Case 3 — Patient starts a new session later: replay into system prompt context

When `GeminiLiveConsumer.connect()` runs and a new Gemini session is being initialised, query for any answered-but-undelivered questions and include them in the **system prompt context block** — not as mid-conversation injections, but as established facts the AI knows from session start.

**File:** `backend/agent/live_consumer.py` — inside `get_patient_context()` (or a dedicated `get_pending_answers_context()` helper):

```python
@database_sync_to_async
def get_pending_answers_context(self):
    from agent.models import PatientQuestion
    pending = PatientQuestion.objects.filter(
        patient=self.patient,
        status='ANSWERED',
        notify_ai_on_answer=True,
        delivered_to_ai=False,
    ).select_related('answered_by').order_by('answered_at')

    if not pending.exists():
        return ""

    lines = ["Pending answers from the care team (relay these to the patient early in the conversation):"]
    for q in pending:
        answered_by = q.answered_by.get_full_name() if q.answered_by else "Care team"
        answered_at = q.answered_at.strftime('%b %d, %I:%M %p') if q.answered_at else ""
        lines.append(
            f"- Patient asked: \"{q.question_text}\"\n"
            f"  {answered_by} answered ({answered_at}): \"{q.answer_text}\""
        )
    return "\n".join(lines)
```

Call this in `run_gemini_session()` alongside `get_patient_context()` and append the result to `system_instruction`. After the session is established, mark all those questions as delivered:

```python
pending_context = await self.get_pending_answers_context()
# ... build system_instruction including pending_context ...

# After session.connect() succeeds, mark delivered
await database_sync_to_async(
    PatientQuestion.objects.filter(
        patient=self.patient, status='ANSWERED', delivered_to_ai=False
    ).update
)(delivered_to_ai=True, delivered_to_ai_at=timezone.now())
```

This way the patient is informed naturally at the start of the next conversation: *"By the way, Dr. Patel answered your question about the dizziness — he said mild dizziness in the first week is expected..."*

---

#### Summary of the three delivery paths

| Scenario | Delivery mechanism | `delivered_to_ai` set by |
|---|---|---|
| Session active when answer is submitted | Channel layer → `input_queue` → `session.send()` — AI responds in real time | `_mark_question_delivered()` in consumer handler |
| Session reconnects within ~60s | Celery polling task re-sends via channel layer | Same consumer handler on receipt |
| Patient offline; starts new session later | Injected into system prompt context on next connect | Bulk update after session established |

---

## 7. Visit Prep Note (AI-Generated)

### Current State

`analytics.HealthReport` exists with a `doctor_visit` type. There is no AI generation logic, no structured data aggregation for visit prep, and no stale-flag mechanism.

---

### 7.1 New Model — `VisitPrepNote`

**File:** `backend/analytics/models.py`

```python
class VisitPrepNote(models.Model):
    patient = models.ForeignKey(
        PatientProfile, on_delete=models.CASCADE, related_name='visit_prep_notes'
    )
    doctor = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='visit_prep_notes',
        limit_choices_to={'user_type': 'DOCTOR'},
    )
    generated_at = models.DateTimeField(auto_now_add=True)
    refreshed_at = models.DateTimeField(null=True, blank=True)
    content = models.TextField(help_text="Markdown or plain-text AI-generated summary")
    data_window_days = models.IntegerField(default=7)
    is_stale = models.BooleanField(default=False)
    generation_params = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'visit_prep_notes'
        ordering = ['-generated_at']
        indexes = [
            models.Index(fields=['patient', '-generated_at']),
        ]

    def __str__(self):
        return f"VisitPrepNote for {self.patient.user.get_full_name()} @ {self.generated_at:%Y-%m-%d}"
```

---

### 7.2 Service Function

**File:** `backend/analytics/services.py` (create if not exists)

```python
import os
from google import genai
from django.conf import settings
from django.utils import timezone
from datetime import timedelta


def generate_visit_prep_note(patient_id: int, doctor_id: int = None) -> 'VisitPrepNote':
    """
    Aggregates the last N days of patient data and calls Gemini (standard API, not live)
    to generate a concise visit preparation note for the doctor.
    """
    from patients.models import PatientProfile
    from vitals.models import VitalReading
    from medications.models import MedicationAdherence
    from agent.models import PatientActivityLog, MoodLog, NutritionLog, PatientQuestion
    from analytics.models import VisitPrepNote
    from users.models import User

    patient = PatientProfile.objects.get(pk=patient_id)
    doctor = User.objects.filter(pk=doctor_id, user_type='DOCTOR').first() if doctor_id else None
    window_days = 7
    since = timezone.now() - timedelta(days=window_days)

    # --- Gather data ---
    vitals = VitalReading.objects.filter(
        patient=patient, measured_at__gte=since
    ).select_related('vital_type').order_by('-measured_at')[:30]

    adherence = MedicationAdherence.objects.filter(
        medication__patient=patient, scheduled_date__gte=since.date()
    ).select_related('medication').order_by('-scheduled_date')

    mood_logs = MoodLog.objects.filter(
        patient=patient, observed_at__gte=since
    ).order_by('-observed_at')[:20]

    nutrition_logs = NutritionLog.objects.filter(
        patient=patient, meal_time__gte=since
    ).order_by('-meal_time')[:20]

    symptoms = PatientActivityLog.objects.filter(
        patient=patient, activity_type='SYMPTOM', observed_at__gte=since
    ).order_by('-observed_at')[:20]

    questions = PatientQuestion.objects.filter(
        patient=patient, asked_at__gte=since
    ).order_by('-asked_at')[:10]

    # --- Build prompt ---
    vitals_text = "\n".join(
        f"- {v.vital_type.name}: {v.get_display_value()} ({v.measured_at:%Y-%m-%d %H:%M})"
        for v in vitals
    ) or "No readings."

    adherence_summary = {}
    for a in adherence:
        name = a.medication.medication_name
        adherence_summary.setdefault(name, {'taken': 0, 'missed': 0, 'skipped': 0})
        adherence_summary[name][a.status.lower()] = adherence_summary[name].get(a.status.lower(), 0) + 1
    adherence_text = "\n".join(
        f"- {name}: taken={v['taken']}, missed={v['missed']}, skipped={v['skipped']}"
        for name, v in adherence_summary.items()
    ) or "No records."

    mood_text = "\n".join(
        f"- {m.observed_at:%Y-%m-%d}: {m.mood_label} (score {m.mood_score})"
        for m in mood_logs
    ) or "No mood logs."

    nutrition_text = "\n".join(
        f"- {n.meal_time:%Y-%m-%d %H:%M}: {n.meal_type}, ~{n.estimated_kcal} kcal — {n.description[:60]}"
        for n in nutrition_logs if n.estimated_kcal
    ) or "No nutrition logs."

    symptoms_text = "\n".join(
        f"- {s.observed_at:%Y-%m-%d %H:%M}: {s.description}"
        for s in symptoms
    ) or "No symptoms reported."

    questions_text = "\n".join(
        f"- {q.asked_at:%Y-%m-%d}: \"{q.question_text}\" [{'Answered' if q.status == 'ANSWERED' else 'Unanswered'}]"
        for q in questions
    ) or "None."

    prompt = f"""You are a clinical documentation assistant. Generate a concise visit preparation note for the doctor.
Write in professional clinical language. Use bullet points. Keep it under 400 words.

Patient: {patient.user.get_full_name()}, Age: {patient.user.age or 'Unknown'}, Gender: {patient.gender}
Conditions: {', '.join(patient.health_conditions) or 'Not specified'}
Period: Last {window_days} days

VITAL SIGNS:
{vitals_text}

MEDICATION ADHERENCE:
{adherence_text}

MOOD:
{mood_text}

NUTRITION:
{nutrition_text}

SYMPTOMS REPORTED:
{symptoms_text}

PATIENT QUESTIONS FOR DOCTOR:
{questions_text}

Generate the visit prep note now:"""

    api_key = os.environ.get("GOOGLE_API_KEY") or getattr(settings, "GOOGLE_API_KEY", None)
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
    )
    content = response.text or "Unable to generate note."

    note, _ = VisitPrepNote.objects.update_or_create(
        patient=patient,
        doctor=doctor,
        defaults={
            'content': content,
            'refreshed_at': timezone.now(),
            'is_stale': False,
            'data_window_days': window_days,
            'generation_params': {'prompt_length': len(prompt)},
        }
    )
    return note
```

---

### 7.3 Celery Task

**File:** `backend/analytics/tasks.py`

```python
from celery import shared_task

@shared_task
def refresh_stale_visit_prep_notes():
    """Runs nightly. Regenerates any VisitPrepNote marked is_stale=True."""
    from analytics.models import VisitPrepNote
    from analytics.services import generate_visit_prep_note

    stale = VisitPrepNote.objects.filter(is_stale=True)
    for note in stale:
        try:
            generate_visit_prep_note(
                patient_id=note.patient_id,
                doctor_id=note.doctor_id,
            )
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Failed to refresh note {note.pk}: {e}")
```

Celery Beat schedule:

```python
'refresh-visit-prep-notes': {
    'task': 'analytics.tasks.refresh_stale_visit_prep_notes',
    'schedule': crontab(hour=2, minute=0),  # 2am daily
},
```

---

### 7.4 Stale Signal

**File:** `backend/analytics/signals.py` (create if not exists)

```python
from django.db.models.signals import post_save
from django.dispatch import receiver


def _mark_visit_prep_stale(patient_id):
    from analytics.models import VisitPrepNote
    VisitPrepNote.objects.filter(patient_id=patient_id, is_stale=False).update(is_stale=True)


@receiver(post_save, sender='vitals.VitalReading')
@receiver(post_save, sender='agent.MoodLog')
@receiver(post_save, sender='agent.NutritionLog')
@receiver(post_save, sender='agent.PatientQuestion')
def mark_stale_on_new_data(sender, instance, created, **kwargs):
    if created:
        _mark_visit_prep_stale(instance.patient_id)
```

Register in `backend/analytics/apps.py`:

```python
def ready(self):
    import analytics.signals  # noqa
```

---

### 7.5 API Endpoints

**File:** `backend/analytics/views.py`

```python
# GET /api/patients/{id}/visit-prep-note/
class VisitPrepNoteView(APIView):
    permission_classes = [IsAuthenticated, CanAccessPatientData]

    def get(self, request, patient_id):
        from analytics.models import VisitPrepNote
        from analytics.services import generate_visit_prep_note

        patient = get_object_or_404(PatientProfile, pk=patient_id)
        self.check_object_permissions(request, patient)

        note = VisitPrepNote.objects.filter(patient=patient).order_by('-generated_at').first()
        if not note or note.is_stale:
            note = generate_visit_prep_note(patient_id=patient.pk)

        return Response(VisitPrepNoteSerializer(note).data)


# POST /api/patients/{id}/visit-prep-note/refresh/
class RefreshVisitPrepNoteView(APIView):
    permission_classes = [IsAuthenticated, IsDoctor]

    def post(self, request, patient_id):
        from analytics.services import generate_visit_prep_note
        patient = get_object_or_404(PatientProfile, pk=patient_id)
        self.check_object_permissions(request, patient)
        note = generate_visit_prep_note(patient_id=patient.pk, doctor_id=request.user.pk)
        return Response(VisitPrepNoteSerializer(note).data)
```

---

## 8. Task & Schedule Calendar with Live AI Feed

### Current State

`family.CareSchedule` handles family-assigned care tasks but is family-member-centric and has no AI awareness. `enhanced_function_definitions.py` has a `schedule_task` tool but it is not in `live_consumer.py`.

---

### 8.1 New Model — `PatientTask`

**File:** `backend/family/models.py`

```python
class PatientTask(models.Model):
    RECURRENCE_CHOICES = [
        ('NONE', 'One-Time'),
        ('DAILY', 'Daily'),
        ('WEEKLY', 'Weekly'),
    ]
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('SKIPPED', 'Skipped'),
    ]

    patient = models.ForeignKey(
        PatientProfile, on_delete=models.CASCADE, related_name='patient_tasks'
    )
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name='created_patient_tasks'
    )
    title = models.CharField(max_length=200)
    instructions = models.TextField(
        blank=True,
        help_text="Plain-English instructions fed to the AI (e.g. 'Please take a photo of your left forearm wound for the nurse to review')"
    )
    scheduled_for = models.DateTimeField()
    recurrence = models.CharField(max_length=10, choices=RECURRENCE_CHOICES, default='NONE')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='PENDING')
    completion_note = models.TextField(blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    requires_image = models.BooleanField(default=False)
    completion_image = models.ImageField(upload_to='task_images/', null=True, blank=True)
    assigned_to_ai = models.BooleanField(
        default=True,
        help_text="If True, the live AI companion will be made aware of and prompt for this task"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'patient_tasks'
        ordering = ['scheduled_for']

    def __str__(self):
        return f"{self.title} — {self.patient.user.get_full_name()} [{self.status}]"
```

---

### 8.2 New Model — `PatientScheduleEntry`

**File:** `backend/family/models.py`

```python
class PatientScheduleEntry(models.Model):
    CATEGORY_CHOICES = [
        ('MEDICATION', 'Medication'),
        ('EXERCISE', 'Exercise'),
        ('MEAL', 'Meal'),
        ('SOCIAL', 'Social Activity'),
        ('OTHER', 'Other'),
    ]

    patient = models.ForeignKey(
        PatientProfile, on_delete=models.CASCADE, related_name='schedule_entries'
    )
    time_of_day = models.TimeField()
    days_of_week = models.JSONField(
        default=list,
        help_text="List of weekday integers [0=Mon … 6=Sun]. Empty = every day."
    )
    description = models.TextField(
        help_text="Plain English: 'Take Metformin 500mg with breakfast' — fed directly to AI context"
    )
    category = models.CharField(max_length=15, choices=CATEGORY_CHOICES, default='OTHER')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'patient_schedule_entries'
        ordering = ['time_of_day']

    def __str__(self):
        return f"{self.time_of_day.strftime('%H:%M')} — {self.description[:50]}"
```

---

### 8.3 Feed Tasks into Live AI Context

**File:** `backend/agent/live_consumer.py`

In `get_patient_context()`, add after the medications query:

```python
# 3. Today's Tasks
from family.models import PatientTask, PatientScheduleEntry
from datetime import date, datetime

today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
today_end = today_start + timedelta(days=1)
today_tasks = PatientTask.objects.filter(
    patient=patient,
    scheduled_for__gte=today_start,
    scheduled_for__lt=today_end,
    assigned_to_ai=True,
    status__in=['PENDING', 'IN_PROGRESS'],
).order_by('scheduled_for')

tasks_lines = []
for i, t in enumerate(today_tasks, 1):
    img_note = " [requires photo]" if t.requires_image else ""
    tasks_lines.append(
        f"{i}) {t.title}{img_note} — {t.scheduled_for.strftime('%H:%M')}. {t.instructions}"
    )
tasks_str = "\n".join(tasks_lines) if tasks_lines else "No tasks assigned for today."

# 4. Fixed daily schedule
today_weekday = timezone.now().weekday()
schedule_entries = PatientScheduleEntry.objects.filter(
    patient=patient,
    is_active=True,
).filter(
    models.Q(days_of_week=[]) | models.Q(days_of_week__contains=today_weekday)
).order_by('time_of_day')

schedule_lines = [
    f"- {e.time_of_day.strftime('%H:%M')}: {e.description}"
    for e in schedule_entries
]
schedule_str = "\n".join(schedule_lines) if schedule_lines else "No fixed schedule entries."
```

Return these in the context dict, and add them to the system prompt:

```python
Today's AI-Assigned Tasks:
{context['tasks']}

Fixed Daily Schedule:
{context['schedule']}
```

---

### 8.4 Tool Declaration — `complete_task`

**File:** `backend/agent/live_consumer.py`

```python
types.FunctionDeclaration(
    name="complete_task",
    description=(
        "Mark a patient task as completed. Call this when the patient confirms they have "
        "completed one of their assigned tasks. If the task requires an image, include the "
        "image data from the camera feed."
    ),
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "task_id_or_title": types.Schema(
                type="STRING",
                description="The task title or ID number as shown in today's task list."
            ),
            "completion_note": types.Schema(
                type="STRING",
                description="Optional brief note about how the task was completed."
            ),
            "image_base64": types.Schema(
                type="STRING",
                description="Base64-encoded JPEG image if the task requires photo confirmation."
            ),
        },
        required=["task_id_or_title"]
    )
),
```

Dispatch in tool loop:

```python
elif fc.name == "complete_task":
    asyncio.create_task(self.handle_complete_task(fc_args, fc_id))
```

Handler method:

```python
async def handle_complete_task(self, args: dict, fc_id):
    result = await self._mark_task_complete(
        args.get('task_id_or_title', ''),
        args.get('completion_note', ''),
        args.get('image_base64')
    )
    if self.session:
        await self.session.send(
            types.FunctionResponse(id=fc_id, name="complete_task", response=result)
        )

@database_sync_to_async
def _mark_task_complete(self, task_id_or_title: str, note: str, image_b64: str) -> dict:
    from family.models import PatientTask
    import base64
    from django.core.files.base import ContentFile

    try:
        patient = PatientProfile.objects.filter(user=self.user).first()
        task = None
        if task_id_or_title.isdigit():
            task = PatientTask.objects.filter(pk=int(task_id_or_title), patient=patient).first()
        if not task:
            task = PatientTask.objects.filter(
                patient=patient,
                title__icontains=task_id_or_title,
                status__in=['PENDING', 'IN_PROGRESS']
            ).order_by('scheduled_for').first()
        if not task:
            return {"success": False, "error": f"Task not found: {task_id_or_title}"}

        task.status = 'COMPLETED'
        task.completed_at = timezone.now()
        task.completion_note = note

        if image_b64 and task.requires_image:
            image_data = base64.b64decode(image_b64)
            task.completion_image.save(
                f'task_{task.pk}_{timezone.now().strftime("%Y%m%d%H%M%S")}.jpg',
                ContentFile(image_data),
                save=False
            )
        task.save()

        # Push notification to task creator
        if task.created_by_id:
            from alerts.services import send_push_notification
            send_push_notification.delay(
                user_ids=[task.created_by_id],
                title=f"Task completed — {patient.user.get_full_name()}",
                body=f'"{task.title}" has been completed.',
                data={'task_id': task.pk, 'patient_id': patient.pk},
            )
        return {"success": True, "message": f"Task '{task.title}' marked completed."}
    except Exception as e:
        logger.error(f"Error completing task: {e}")
        return {"success": False, "error": str(e)}
```

---

### 8.5 CRUD API Endpoints

**File:** `backend/family/views.py` — add:

```
GET/POST  /api/patients/{id}/tasks/
GET/PUT/DELETE /api/patients/{id}/tasks/{task_id}/

GET/POST  /api/patients/{id}/schedule/
GET/PUT/DELETE /api/patients/{id}/schedule/{entry_id}/
```

Apply `IsFamilyOrDoctor` and `CanAccessPatientData` permissions.

---

## 9. Messaging System

### Current State

`family.FamilyCommunication` links `FamilyMember` to `FamilyMember` — it cannot represent doctor-to-patient or clinician messages. There is no delivery of messages to the live AI session.

---

### 9.1 New Model — `Message`

**File:** `backend/family/models.py`

```python
class Message(models.Model):
    MESSAGE_TYPE_CHOICES = [
        ('TEXT', 'General Text'),
        ('CARE_INSTRUCTION', 'Care Instruction'),
        ('ANSWER', 'Answer to Patient Question'),
    ]

    sender = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='sent_messages'
    )
    recipient_patient = models.ForeignKey(
        PatientProfile, on_delete=models.CASCADE, related_name='messages'
    )
    content = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
    delivered_to_ai = models.BooleanField(default=False)
    delivered_to_ai_at = models.DateTimeField(null=True, blank=True)
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPE_CHOICES, default='TEXT')

    class Meta:
        db_table = 'messages'
        ordering = ['-sent_at']
        indexes = [
            models.Index(fields=['recipient_patient', '-sent_at']),
            models.Index(fields=['delivered_to_ai', '-sent_at']),
        ]

    def __str__(self):
        return f"From {self.sender.get_full_name()} → {self.recipient_patient.user.get_full_name()}: {self.content[:60]}"
```

---

### 9.2 API Endpoints

**File:** `backend/family/views.py`

```python
# POST /api/patients/{id}/messages/
# GET  /api/patients/{id}/messages/
class PatientMessageView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsFamilyOrDoctor, CanAccessPatientData]
    serializer_class = MessageSerializer

    def get_queryset(self):
        return Message.objects.filter(recipient_patient_id=self.kwargs['patient_id'])

    def perform_create(self, serializer):
        patient = get_object_or_404(PatientProfile, pk=self.kwargs['patient_id'])
        self.check_object_permissions(self.request, patient)
        message = serializer.save(sender=self.request.user, recipient_patient=patient)
        self._deliver_to_ai(message)

    def _deliver_to_ai(self, message: 'Message'):
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'patient_{message.recipient_patient_id}_agent',
            {
                'type': 'message.incoming',
                'message_id': message.pk,
                'sender_name': message.sender.get_full_name(),
                'content': message.content,
                'message_type': message.message_type,
            }
        )
```

---

### 9.3 Message Delivery in `live_consumer.py`

Add channel message handler:

```python
async def message_incoming(self, event):
    """Receives a message from a family member or doctor via the channel layer."""
    sender_name = event['sender_name']
    content = event['content']
    message_id = event['message_id']

    inject_text = (
        f"[System: You have received an incoming message for the patient.] "
        f"Message from {sender_name}: \"{content}\". "
        f"Please relay this message to the patient in a warm, conversational way."
    )

    if self.session:
        await self.session.send(input=types.Content(
            parts=[types.Part(text=inject_text)],
            role='user'
        ))

    # Mark delivered
    await self._mark_message_delivered(message_id)

@database_sync_to_async
def _mark_message_delivered(self, message_id: int):
    from family.models import Message
    Message.objects.filter(pk=message_id).update(
        delivered_to_ai=True, delivered_to_ai_at=timezone.now()
    )
```

On session connect, replay undelivered messages:

```python
@database_sync_to_async
def get_undelivered_messages(self):
    from family.models import Message
    patient = PatientProfile.objects.filter(user=self.user).first()
    if not patient:
        return []
    return list(
        Message.objects.filter(
            recipient_patient=patient, delivered_to_ai=False
        ).select_related('sender').order_by('sent_at')[:10]
    )
```

In `run_gemini_session()`, after building the system instruction and before the main loop, inject undelivered messages:

```python
undelivered = await self.get_undelivered_messages()
if undelivered:
    messages_block = "\n".join(
        f"- From {m.sender.get_full_name()}: \"{m.content}\""
        for m in undelivered
    )
    system_instruction += f"\n\nUndelivered messages (relay these naturally early in conversation):\n{messages_block}"
    # Mark delivered
    from asgiref.sync import sync_to_async
    from family.models import Message
    await sync_to_async(
        Message.objects.filter(pk__in=[m.pk for m in undelivered]).update
    )(delivered_to_ai=True, delivered_to_ai_at=timezone.now())
```

---

## 10. Push Notification Infrastructure

### Current State

`alerts.AlertDelivery` has a `PUSH` channel choice and `NotificationPreference` has a `push_device_tokens` JSONField, but there is no `PushDevice` model, no Firebase Admin SDK integration, and no actual send logic.

---

### 10.1 New Model — `PushDevice`

**File:** `backend/alerts/models.py`

```python
class PushDevice(models.Model):
    PLATFORM_CHOICES = [
        ('FCM', 'Firebase Cloud Messaging (Android)'),
        ('APNS', 'Apple Push Notification Service (iOS)'),
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='push_devices'
    )
    token = models.TextField(help_text="FCM or APNs device registration token")
    platform = models.CharField(max_length=5, choices=PLATFORM_CHOICES)
    device_name = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'push_devices'
        unique_together = ['user', 'token']

    def __str__(self):
        return f"{self.user.get_full_name()} — {self.platform} [{self.device_name}]"
```

---

### 10.2 Device Registration Endpoint

**File:** `backend/alerts/views.py`

```python
# POST /api/notifications/devices/
class RegisterPushDeviceView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from alerts.models import PushDevice
        token = request.data.get('token', '').strip()
        platform = request.data.get('platform', '').upper()
        device_name = request.data.get('device_name', '')

        if not token or platform not in ('FCM', 'APNS'):
            return Response({'error': 'token and platform (FCM|APNS) required'}, status=400)

        device, created = PushDevice.objects.update_or_create(
            user=request.user,
            token=token,
            defaults={'platform': platform, 'device_name': device_name, 'is_active': True},
        )
        return Response({'registered': True, 'created': created})
```

---

### 10.3 Send Utility & Celery Task

**File:** `backend/alerts/services.py`

```python
import firebase_admin
from firebase_admin import credentials, messaging
from django.conf import settings
from celery import shared_task
import logging

logger = logging.getLogger(__name__)

# Initialize Firebase Admin SDK once
_firebase_initialized = False

def _get_firebase_app():
    global _firebase_initialized
    if not _firebase_initialized:
        cred_path = getattr(settings, 'FIREBASE_CREDENTIALS_PATH', None)
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        _firebase_initialized = True
    return firebase_admin.get_app()


@shared_task(bind=True, max_retries=3)
def send_push_notification(self, user_ids: list, title: str, body: str, data: dict = None):
    """
    Send push notification to all active devices of the given user IDs.
    Uses Firebase Admin SDK for both FCM (Android) and APNs (iOS via FCM).
    """
    from alerts.models import PushDevice
    from django.utils import timezone

    _get_firebase_app()
    data = {str(k): str(v) for k, v in (data or {}).items()}  # FCM requires string values

    devices = PushDevice.objects.filter(user_id__in=user_ids, is_active=True)
    if not devices.exists():
        return

    messages_batch = []
    for device in devices:
        msg = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            data=data,
            token=device.token,
        )
        messages_batch.append(msg)

    if not messages_batch:
        return

    try:
        response = messaging.send_each(messages_batch)
        # Deactivate tokens that returned invalid-registration errors
        for i, resp in enumerate(response.responses):
            if not resp.success:
                err_code = resp.exception.code if resp.exception else ''
                if err_code in ('registration-token-not-registered', 'invalid-registration-token'):
                    devices[i].is_active = False
                    devices[i].save(update_fields=['is_active'])
        logger.info(f"Push sent: {response.success_count} ok, {response.failure_count} failed")
    except Exception as exc:
        logger.error(f"Push notification failed: {exc}")
        raise self.retry(exc=exc, countdown=60)
```

**Settings required** (in `backend/carepal/settings.py`):

```python
FIREBASE_CREDENTIALS_PATH = env('FIREBASE_CREDENTIALS_PATH', default='/etc/secrets/firebase-adminsdk.json')
```

**requirements.txt**: add `firebase-admin>=6.0.0`

---

### 10.4 Alert Creation Trigger

**File:** `backend/alerts/signals.py` (create or add to existing)

```python
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender='alerts.Alert')
def push_alert_on_create(sender, instance, created, **kwargs):
    if not created:
        return
    from alerts.services import send_push_notification
    from family.models import FamilyMember
    from users.models import ClinicalRelationship

    patient = instance.patient
    family_ids = list(FamilyMember.objects.filter(patient=patient, is_active=True).values_list('user_id', flat=True))
    doctor_ids = list(ClinicalRelationship.objects.filter(patient=patient, is_active=True).values_list('doctor_id', flat=True))
    all_ids = list(set(family_ids + doctor_ids))
    if all_ids:
        send_push_notification.delay(
            user_ids=all_ids,
            title=instance.title,
            body=instance.message[:200],
            data={'alert_id': instance.pk, 'severity': instance.severity, 'patient_id': patient.pk},
        )
```

---

### 10.5 Push Triggers Summary

The following places should call `send_push_notification.delay(...)`:

| Trigger | Location |
|---|---|
| `Alert` created | `alerts/signals.py` (above) |
| `EscalationEvent` created | `alerts/tasks.detect_multi_signal_escalation` |
| `PatientQuestion` logged | `live_consumer._save_patient_question` |
| Task completed | `live_consumer._mark_task_complete` |
| Incoming message | `family/views.PatientMessageView.perform_create` — push to patient's emergency contacts if needed |

---

## 11. Family Home Screen — AI-Generated Summary Cards

### Current State

`analytics.DashboardSnapshot` stores raw structured data. There are no AI-generated plain-language card objects and no WebSocket push to family on data change.

---

### 11.1 New Model — `FamilySummaryCard`

**File:** `backend/analytics/models.py`

```python
class FamilySummaryCard(models.Model):
    patient = models.ForeignKey(
        PatientProfile, on_delete=models.CASCADE, related_name='family_summary_cards'
    )
    generated_at = models.DateTimeField(auto_now_add=True)
    generated_for_date = models.DateField()
    is_stale = models.BooleanField(default=False)
    cards = models.JSONField(
        default=list,
        help_text="""Array of card objects:
        [
          {
            "category": "vitals|medications|mood|nutrition|sleep|overall",
            "headline": "Blood pressure stable today",
            "detail": "Two readings taken, both within normal range.",
            "severity": "ok|warning|critical",
            "tap_target": "vitals"
          }
        ]"""
    )

    class Meta:
        db_table = 'family_summary_cards'
        ordering = ['-generated_at']
        unique_together = ['patient', 'generated_for_date']

    def __str__(self):
        return f"FamilySummary for {self.patient.user.get_full_name()} on {self.generated_for_date}"
```

---

### 11.2 Service Function

**File:** `backend/analytics/services.py`

```python
def generate_family_summary(patient_id: int) -> 'FamilySummaryCard':
    import json
    from django.utils import timezone
    from patients.models import PatientProfile
    from vitals.models import VitalReading
    from medications.models import MedicationAdherence
    from agent.models import PatientActivityLog, MoodLog, NutritionLog
    from analytics.models import FamilySummaryCard

    patient = PatientProfile.objects.get(pk=patient_id)
    today = timezone.now().date()
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)

    # Gather today's data
    vitals_today = list(VitalReading.objects.filter(
        patient=patient, measured_at__gte=today_start
    ).select_related('vital_type').order_by('-measured_at')[:10])

    adherence_today = list(MedicationAdherence.objects.filter(
        medication__patient=patient, scheduled_date=today
    ).select_related('medication'))

    mood_today = list(MoodLog.objects.filter(
        patient=patient, observed_at__gte=today_start
    ).order_by('-observed_at')[:5])

    nutrition_today = list(NutritionLog.objects.filter(
        patient=patient, meal_time__gte=today_start
    ))

    sleep_last_night = PatientActivityLog.objects.filter(
        patient=patient,
        activity_type='SLEEP',
        observed_at__gte=today_start - timezone.timedelta(hours=10),
        observed_at__lte=today_start + timezone.timedelta(hours=2),
    ).order_by('-observed_at').first()

    # Build raw data summary for Gemini
    vitals_text = "\n".join(
        f"- {v.vital_type.name}: {v.get_display_value()} at {v.measured_at.strftime('%H:%M')}"
        for v in vitals_today
    ) or "No vitals recorded today."

    meds_taken = sum(1 for a in adherence_today if a.status == 'TAKEN')
    meds_total = len(adherence_today)
    meds_text = f"{meds_taken}/{meds_total} medications taken today." if meds_total else "No medications scheduled."

    mood_text = (
        f"Last recorded: {mood_today[0].mood_label} (score {mood_today[0].mood_score})"
        if mood_today else "No mood data today."
    )

    total_kcal = sum(n.estimated_kcal or 0 for n in nutrition_today)
    nutrition_text = f"Estimated {total_kcal} kcal consumed today across {len(nutrition_today)} meal entries." if nutrition_today else "No meals logged today."

    sleep_text = sleep_last_night.description if sleep_last_night else "No sleep data."

    prompt = f"""You are generating summary cards for a family member caring for a patient.
Output ONLY a valid JSON array. Each card has: category, headline, detail, severity.
- category: one of "vitals", "medications", "mood", "nutrition", "sleep", "overall"
- headline: short (under 10 words), plain English, NO raw numbers in headline
- detail: one sentence with specific values allowed
- severity: "ok", "warning", or "critical"

Generate one card per category (only include categories with data). Be warm and non-alarming unless genuinely concerning.

Data for {patient.user.get_full_name()} today ({today}):
VITALS: {vitals_text}
MEDICATIONS: {meds_text}
MOOD: {mood_text}
NUTRITION: {nutrition_text}
SLEEP: {sleep_text}

Output JSON array only:"""

    api_key = os.environ.get("GOOGLE_API_KEY") or getattr(settings, "GOOGLE_API_KEY", None)
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)

    try:
        raw = response.text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        cards = json.loads(raw)
    except Exception:
        cards = [{"category": "overall", "headline": "Summary unavailable", "detail": "Could not generate summary.", "severity": "ok"}]

    summary, _ = FamilySummaryCard.objects.update_or_create(
        patient=patient,
        generated_for_date=today,
        defaults={'cards': cards, 'is_stale': False},
    )
    return summary
```

---

### 11.3 Stale Signal

**File:** `backend/analytics/signals.py` — add to existing signal handlers:

```python
def _mark_family_summary_stale(patient_id):
    from analytics.models import FamilySummaryCard
    from django.utils import timezone
    FamilySummaryCard.objects.filter(
        patient_id=patient_id,
        generated_for_date=timezone.now().date(),
        is_stale=False
    ).update(is_stale=True)

@receiver(post_save, sender='vitals.VitalReading')
@receiver(post_save, sender='medications.MedicationAdherence')
@receiver(post_save, sender='agent.MoodLog')
@receiver(post_save, sender='agent.NutritionLog')
@receiver(post_save, sender='agent.PatientActivityLog')
def mark_family_summary_stale(sender, instance, created, **kwargs):
    if created:
        _mark_family_summary_stale(instance.patient_id)
        # Trigger debounced regeneration
        from analytics.tasks import regenerate_family_summary_debounced
        regenerate_family_summary_debounced.apply_async(
            args=[instance.patient_id], countdown=60
        )
```

---

### 11.4 Celery Task (Debounced)

**File:** `backend/analytics/tasks.py`

```python
@shared_task
def regenerate_family_summary_debounced(patient_id: int):
    """
    Regenerates FamilySummaryCard if still stale (debounces: if called multiple
    times within 60s, only the last invocation that finds is_stale=True runs).
    After generation, pushes WebSocket event to family viewers.
    """
    from analytics.models import FamilySummaryCard
    from analytics.services import generate_family_summary
    from django.utils import timezone
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync

    today = timezone.now().date()
    if not FamilySummaryCard.objects.filter(
        patient_id=patient_id, generated_for_date=today, is_stale=True
    ).exists():
        return  # Already regenerated or not stale

    summary = generate_family_summary(patient_id)

    # Push WebSocket update to family viewers
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f'patient_{patient_id}_updates',
        {
            'type': 'summary_updated',
            'data': {
                'generated_at': summary.generated_at.isoformat(),
                'cards': summary.cards,
            }
        }
    )
```

---

### 11.5 API Endpoint

**File:** `backend/analytics/views.py`

```python
# GET /api/patients/{id}/family-summary/
class FamilySummaryView(APIView):
    permission_classes = [IsAuthenticated, IsFamilyOrDoctor, CanAccessPatientData]

    def get(self, request, patient_id):
        from analytics.models import FamilySummaryCard
        from analytics.services import generate_family_summary
        from django.utils import timezone

        patient = get_object_or_404(PatientProfile, pk=patient_id)
        self.check_object_permissions(request, patient)

        today = timezone.now().date()
        summary = FamilySummaryCard.objects.filter(
            patient=patient, generated_for_date=today
        ).first()

        if not summary or summary.is_stale:
            summary = generate_family_summary(patient_id=patient.pk)

        return Response(FamilySummaryCardSerializer(summary).data)
```

---

## Migration Checklist

Run migrations in this order after implementing all models:

```bash
python manage.py makemigrations users          # ClinicalRelationship
python manage.py makemigrations patients       # daily_calorie_target, mood_baseline_score fields
python manage.py makemigrations medications    # confirmation_method field on MedicationAdherence
python manage.py makemigrations agent          # NutritionLog, MoodLog, PatientQuestion
python manage.py makemigrations family         # PatientTask, PatientScheduleEntry, Message
python manage.py makemigrations alerts         # EscalationEvent, EscalationStep, PushDevice
python manage.py makemigrations analytics      # VisitPrepNote, FamilySummaryCard
python manage.py migrate
```

---

## New URL Registrations Summary

**File:** `backend/carepal/urls.py` or each app's `urls.py`:

| Method | URL | View | Permission |
|---|---|---|---|
| GET/POST | `/api/patients/{id}/tasks/` | `PatientTaskView` | FAMILY, DOCTOR |
| GET/PUT/DELETE | `/api/patients/{id}/tasks/{task_id}/` | `PatientTaskDetailView` | FAMILY, DOCTOR |
| GET/POST | `/api/patients/{id}/schedule/` | `ScheduleEntryView` | FAMILY, DOCTOR |
| GET/POST | `/api/patients/{id}/messages/` | `PatientMessageView` | FAMILY, DOCTOR |
| POST | `/api/questions/{id}/answer/` | `AnswerPatientQuestionView` | FAMILY, DOCTOR |
| GET | `/api/patients/{id}/visit-prep-note/` | `VisitPrepNoteView` | FAMILY, DOCTOR |
| POST | `/api/patients/{id}/visit-prep-note/refresh/` | `RefreshVisitPrepNoteView` | DOCTOR only |
| GET | `/api/patients/{id}/family-summary/` | `FamilySummaryView` | FAMILY, DOCTOR |
| GET | `/api/patients/{id}/escalations/` | `EscalationEventListView` | FAMILY, DOCTOR |
| GET | `/api/patients/{id}/escalations/{event_id}/steps/` | `EscalationStepListView` | FAMILY, DOCTOR |
| POST | `/api/notifications/devices/` | `RegisterPushDeviceView` | Any authenticated |

---

## WebSocket Routing Summary

**File:** `backend/carepal/routing.py`:

```python
from channels.routing import URLRouter
from django.urls import path

websocket_urlpatterns = [
    path('ws/live/', GeminiLiveConsumer.as_asgi()),                              # PATIENT only
    path('ws/remote-viewer/<int:patient_id>/', RemoteViewerConsumer.as_asgi()), # FAMILY/DOCTOR
]
```

---

## Channel Groups Reference

| Group Name | Who joins | What is sent |
|---|---|---|
| `patient_{id}_agent` | `GeminiLiveConsumer` (patient) | `question.answered`, `message.incoming` |
| `patient_{id}_updates` | `RemoteViewerConsumer` (family/doctor) | `vital_recorded`, `activity_logged`, `alert_created`, `summary_updated` |

---

## Required Package Additions

```
firebase-admin>=6.0.0
python-dateutil>=2.8  (already likely present)
```

---

## Environment Variables Required

```
GOOGLE_API_KEY=...                     # Already present
FIREBASE_CREDENTIALS_PATH=/path/to/firebase-adminsdk.json
```

---

*End of document.*
