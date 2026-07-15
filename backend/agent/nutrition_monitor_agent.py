import logging
from datetime import date, timedelta

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are the CarePal Nutrition Monitor Agent. You receive a meal-related activity log
from a patient's conversation with the CarePal Live AI assistant, along with context
about what the patient has already eaten today.

Your job is to call exactly ONE tool:

1. create_nutrition_log — parse the description into a structured meal record with
   estimated calories and food items.
2. request_clarification — the description is too vague to estimate
   (e.g. "had some food", "ate something").
3. do_nothing — the log is not actually a meal event, or a NutritionLog already
   exists for this entry.

## Deciding which tool to use

### create_nutrition_log
Use when the patient clearly described what they ate and you can make a reasonable
calorie estimate.
- Use common nutritional knowledge for average portions when quantities are not stated.
- Break the meal into individual items with per-item kcal that sum to estimated_kcal.
- Confidence must be ≥ 0.6 or use request_clarification instead.
- Infer meal_type from the time of log and description context.

### request_clarification
Use when the description is genuinely too vague to estimate calories AND a specific
question would resolve it. Do NOT use for minor uncertainty — a best estimate is fine.

### do_nothing
Use when:
- The log is not an actual meal event (patient discussing food in general).
- The context shows a NutritionLog already exists for this activity log.

## General rules
- NEVER create duplicate logs.
- Appetite should only be set if the patient mentioned it.
- You must call exactly one tool. Do not respond with plain text.
"""

TOOLS = [
    {
        "name": "create_nutrition_log",
        "description": (
            "Create a structured NutritionLog from the patient's meal description. "
            "Parse the description into meal type, individual food items with kcal estimates, "
            "and total estimated_kcal. "
            "Do NOT call this if a NutritionLog already exists for this activity log."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "meal_type": {
                    "type": "string",
                    "enum": ["BREAKFAST", "LUNCH", "DINNER", "SNACK", "OTHER"],
                    "description": "Type of meal inferred from time and context.",
                },
                "estimated_kcal": {
                    "type": "integer",
                    "description": (
                        "Total estimated kilocalories for this meal. "
                        "Sum of all item kcal values."
                    ),
                },
                "items": {
                    "type": "array",
                    "description": "Individual food items parsed from the description.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Name of the food item.",
                            },
                            "qty": {
                                "type": "string",
                                "description": "Quantity, e.g. '1 cup', '2 pieces', '1 medium'.",
                            },
                            "kcal": {
                                "type": "integer",
                                "description": "Estimated kcal for this item.",
                            },
                        },
                        "required": ["name", "kcal"],
                    },
                },
                "appetite": {
                    "type": "string",
                    "enum": ["GOOD", "NORMAL", "POOR"],
                    "description": "Patient's reported appetite. Only set if explicitly mentioned.",
                },
                "confidence": {
                    "type": "number",
                    "description": (
                        "Your confidence 0.0–1.0. "
                        "Below 0.6 use request_clarification instead."
                    ),
                },
            },
            "required": ["meal_type", "estimated_kcal", "confidence"],
        },
    },
    {
        "name": "request_clarification",
        "description": (
            "Queue a follow-up question to be asked by the Live AI in the next session. "
            "Use only when the description is too vague to estimate calories at all."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The question for the Live AI to ask the patient naturally.",
                },
                "context": {
                    "type": "string",
                    "description": "Internal context explaining why this is being asked.",
                },
                "priority": {
                    "type": "integer",
                    "description": "1 (urgent) to 10 (low). Default 5.",
                },
            },
            "required": ["question", "context"],
        },
    },
    {
        "name": "do_nothing",
        "description": "Take no action.",
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Brief internal reason.",
                },
            },
            "required": ["reason"],
        },
    },
]


class NutritionMonitorAgent:

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
        from .models import NutritionLog

        # Duplicate guard — if a NutritionLog already exists for this log, skip
        if NutritionLog.objects.filter(source_activity_log=log).exists():
            logger.info(
                f"[NutAgent] NutritionLog already exists for log {log.id}, skipping"
            )
            return

        context = self._build_context(log)
        function_declarations = self._build_function_declarations(gtypes)

        try:
            response = self.client.models.generate_content(
                model='gemini-2.5-flash',
                contents=context,
                config=gtypes.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    tools=[gtypes.Tool(function_declarations=function_declarations)],
                    tool_config=gtypes.ToolConfig(
                        function_calling_config=gtypes.FunctionCallingConfig(mode='ANY')
                    ),
                    temperature=0.1,
                ),
            )

            for part in response.candidates[0].content.parts:
                if part.function_call:
                    self._dispatch(part.function_call, log)
                    break
            else:
                logger.warning(
                    f"[NutAgent] No function call in response for log {log.id}"
                )

        except Exception as e:
            logger.error(f"[NutAgent] Gemini call failed for log {log.id}: {e}")
            raise

    def _build_function_declarations(self, gtypes):
        declarations = []
        for t in TOOLS:
            props = {}
            for k, v in t['parameters']['properties'].items():
                if v.get('type') == 'array':
                    # Handle nested object array (items list)
                    item_props = {
                        pk: gtypes.Schema(
                            type=pv.get('type', 'STRING').upper(),
                            description=pv.get('description', ''),
                        )
                        for pk, pv in v['items']['properties'].items()
                    }
                    props[k] = gtypes.Schema(
                        type='ARRAY',
                        description=v.get('description', ''),
                        items=gtypes.Schema(
                            type='OBJECT',
                            properties=item_props,
                            required=v['items'].get('required', []),
                        ),
                    )
                else:
                    props[k] = gtypes.Schema(
                        type=v.get('type', 'STRING').upper(),
                        description=v.get('description', ''),
                        enum=v.get('enum'),
                    )
            declarations.append(
                gtypes.FunctionDeclaration(
                    name=t['name'],
                    description=t['description'],
                    parameters=gtypes.Schema(
                        type='OBJECT',
                        properties=props,
                        required=t['parameters'].get('required', []),
                    ),
                )
            )
        return declarations

    def _dispatch(self, fc, log) -> None:
        args = dict(fc.args)
        logger.info(f"[NutAgent] Tool: {fc.name} | args: {args} | log: {log.id}")

        if fc.name == 'create_nutrition_log':
            self._create_nutrition_log(
                log=log,
                meal_type=args.get('meal_type', 'OTHER'),
                estimated_kcal=int(args.get('estimated_kcal', 0)),
                items=list(args.get('items', [])),
                appetite=args.get('appetite', ''),
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
            logger.info(
                f"[NutAgent] do_nothing for log {log.id}: {args.get('reason', '')}"
            )

    def _create_nutrition_log(
        self, log, meal_type: str, estimated_kcal: int,
        items: list, appetite: str, confidence: float,
    ) -> None:
        from .models import NutritionLog
        from .nutrition_utils import get_threshold_kcal, get_daily_kcal_total, get_consecutive_low_days

        if confidence < 0.6:
            logger.warning(
                f"[NutAgent] Skipping — confidence {confidence} below 0.6 for log {log.id}"
            )
            return

        patient = log.patient
        today = date.today()

        nutrition_log = NutritionLog.objects.create(
            patient=patient,
            meal_time=log.observed_at,
            meal_type=meal_type,
            description=log.description,
            estimated_kcal=estimated_kcal,
            items=items,
            appetite=appetite,
            source_activity_log=log,
        )

        logger.info(
            f"[NutAgent] Created NutritionLog {nutrition_log.id}: "
            f"{meal_type} ~{estimated_kcal} kcal "
            f"({len(items)} items, confidence={confidence}, log={log.id})"
        )

        # Reactive threshold check — runs immediately, no nightly batch needed
        self._check_threshold(patient, today)

    def _check_threshold(self, patient, today) -> None:
        from .nutrition_utils import get_threshold_kcal, get_daily_kcal_total, get_consecutive_low_days
        from alerts.models import Alert, AlertType

        threshold = get_threshold_kcal(patient)
        if threshold is None:
            return  # No calorie target set — nothing to check

        daily_total = get_daily_kcal_total(patient.id, today)

        if daily_total >= threshold:
            return  # Above threshold — all good

        consecutive = get_consecutive_low_days(patient, today, window=3)
        if consecutive < 2:
            return  # Single low day — not yet alertable

        alert_type, _ = AlertType.objects.get_or_create(
            code='NUTRITION_LOW',
            defaults={
                'name': 'Low Nutrition Intake',
                'category': 'HEALTH_TREND',
                'default_severity': 'WARNING',
                'default_channels': ['IN_APP'],
            },
        )

        # Avoid duplicate alerts for the same patient on the same day
        if Alert.objects.filter(
            alert_type=alert_type,
            patient=patient,
            created_at__date=today,
        ).exists():
            return

        Alert.objects.create(
            alert_type=alert_type,
            patient=patient,
            severity='WARNING',
            title='Low Nutrition Alert',
            message=(
                f"Caloric intake ({daily_total} kcal) is below "
                f"{patient.nutrition_alert_threshold_percent}% of daily target "
                f"({patient.daily_calorie_target} kcal) "
                f"for {consecutive} consecutive days."
            ),
            context_data={
                'today_kcal': daily_total,
                'target_kcal': patient.daily_calorie_target,
                'threshold_kcal': threshold,
                'consecutive_low_days': consecutive,
            },
        )
        logger.info(
            f"[NutAgent] Created NUTRITION_LOW alert for patient {patient.id} "
            f"({daily_total}/{patient.daily_calorie_target} kcal, "
            f"{consecutive} consecutive low days)"
        )

    def _queue_clarification(
        self, log, question: str, context: str, priority: int
    ) -> None:
        from .models import PendingQuestion

        PendingQuestion.objects.create(
            patient=log.patient,
            question=question,
            context=context,
            source='NUTRITION_AGENT',
            source_object_type='PatientActivityLog',
            source_object_id=log.id,
            priority=priority,
            expires_at=timezone.now() + timedelta(hours=6),
        )
        logger.info(
            f"[NutAgent] Queued clarification for log {log.id}: '{question}'"
        )

    def _build_context(self, log) -> str:
        from .models import NutritionLog

        patient = log.patient
        today = date.today()

        today_logs = NutritionLog.objects.filter(
            patient=patient,
            meal_time__date=today,
        ).order_by('meal_time')

        today_lines = [
            f"  - {nl.meal_type} ~{nl.estimated_kcal} kcal: {nl.description}"
            for nl in today_logs
        ] or ['  (none yet)']

        today_kcal = sum(nl.estimated_kcal or 0 for nl in today_logs)
        target = patient.daily_calorie_target
        target_str = (
            f"{today_kcal} / {target} kcal"
            if target
            else f"{today_kcal} kcal logged (no target set)"
        )

        return f"""PATIENT: {patient.user.get_full_name()}
DATE: {today}
TIME OF LOG: {log.observed_at.strftime('%Y-%m-%d %H:%M')}

WHAT THE PATIENT SAID (activity log description):
"{log.description}"

TODAY'S NUTRITION LOGS ALREADY RECORDED:
{chr(10).join(today_lines)}
DAILY TOTAL SO FAR: {target_str}
"""
