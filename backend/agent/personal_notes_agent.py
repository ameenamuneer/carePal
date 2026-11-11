"""
PersonalNotesAgent — keeps PatientProfile.personal_notes up to date.

After a live session ends, an LLM reads the session's conversation, the
patient's profile and the current personal notes, and rewrites the notes: new
lasting facts are added, outdated or contradicted ones removed, everything kept
short. The notes are injected into the live AI's system prompt at the start of
every session, so they must stay small and easy to digest.

Triggered by agent.tasks.update_personal_notes (dispatched from
GeminiLiveConsumer.disconnect).
"""

import logging
from datetime import datetime

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

MODEL = 'gemini-2.5-flash'

# ~300 tokens: roughly 10–15 short bullets, small next to the rest of the live
# system prompt. Notes are always written in English (compact, and consistent
# across sessions held in Malayalam, Tamil, Hindi or English).
PERSONAL_NOTES_MAX_CHARS = 1200

# Bound the transcript sent to the model (most recent part wins).
MAX_TRANSCRIPT_CHARS = 30000

NO_CHANGE = "NO_CHANGE"

INSTRUCTIONS = f"""You maintain the PERSONAL NOTES of a home-care patient. A voice AI companion reads
these notes at the start of every conversation to know the person better.

You get the patient's profile, the current notes and the transcript of the latest
conversation. Return the complete, updated notes.

What belongs in the notes — lasting, personal facts the patient stated:
- how they like to be addressed, languages they speak and prefer
- family members, friends, pets (names and relationships)
- daily routine and habits (wake/sleep times, walks, prayer, TV, meals they like)
- interests, hobbies, favourite topics, likes and dislikes
- recurring worries, goals or plans that matter beyond today
- what helps in conversation (e.g. "prefers short answers", "dislikes being reminded twice")

What does NOT belong:
- vitals, medications, doses, meals or symptoms of a single day (tracked elsewhere)
- anything only the AI said, guesses, or unclear/garbled transcript lines
- one-off small talk or transient states ("tired today") unless they recur
- anything already in the profile below

Rules:
- Keep every existing note that is still true; update or remove notes the
  conversation contradicts or makes obsolete.
- Write in English, as short bullet lines starting with "- ", grouped under these
  headings when they have content: "About:", "Routine:", "Interests:",
  "Concerns & goals:", "Conversation tips:". Omit empty headings.
- Telegraphic style, no filler. Hard limit: {PERSONAL_NOTES_MAX_CHARS} characters in total.
  If over, merge or drop the least useful notes.
- If nothing new or changed, reply with exactly {NO_CHANGE}.
- Reply with the notes only (or {NO_CHANGE}), no preamble."""


class PersonalNotesAgent:

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

    def process(self, patient, since: datetime) -> None:
        """Update `patient.personal_notes` from the conversation since `since`."""
        from .models import AgentMessage

        messages = list(
            AgentMessage.objects.filter(
                session__patient=patient, timestamp__gte=since
            ).order_by('timestamp')
        )
        if not any(m.sender == 'USER' for m in messages):
            logger.info(f"PersonalNotesAgent: no patient speech since {since}; skipping.")
            return

        transcript = "\n".join(
            f"[{timezone.localtime(m.timestamp):%H:%M}] "
            f"{'PATIENT' if m.sender == 'USER' else 'AI'}: {m.content}"
            for m in messages
        )[-MAX_TRANSCRIPT_CHARS:]
        current = (patient.personal_notes or "").strip()

        prompt = (
            f"PATIENT PROFILE:\n{self._profile_summary(patient)}\n\n"
            f"CURRENT PERSONAL NOTES:\n{current or '(empty)'}\n\n"
            f"LATEST CONVERSATION ({timezone.localtime(since):%Y-%m-%d}):\n{transcript}"
        )
        notes = self._generate(prompt)
        if notes is None or notes == NO_CHANGE or notes == current:
            logger.info("PersonalNotesAgent: notes unchanged.")
            return

        if len(notes) > PERSONAL_NOTES_MAX_CHARS:
            # One more pass to compress, then hard-trim on a line boundary.
            shorter = self._generate(
                f"Compress these notes to at most {PERSONAL_NOTES_MAX_CHARS} characters, "
                f"keeping the most useful facts and the same format:\n\n{notes}"
            )
            if shorter and shorter != NO_CHANGE:
                notes = shorter
            if len(notes) > PERSONAL_NOTES_MAX_CHARS:
                notes = notes[:PERSONAL_NOTES_MAX_CHARS].rsplit("\n", 1)[0]

        patient.personal_notes = notes
        patient.personal_notes_updated_at = timezone.now()
        patient.save(update_fields=['personal_notes', 'personal_notes_updated_at'])
        logger.info(f"PersonalNotesAgent: notes updated ({len(notes)} chars).")

    def _generate(self, prompt: str):
        from google.genai import types as gtypes
        response = self.client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=gtypes.GenerateContentConfig(
                system_instruction=INSTRUCTIONS,
                temperature=0.2,
            ),
        )
        text = (response.text or "").strip()
        return text or None

    @staticmethod
    def _profile_summary(patient) -> str:
        user = patient.user
        location = ", ".join(p for p in (patient.city, patient.state, patient.country) if p)
        lines = [
            f"Name: {user.get_full_name() or user.username}",
            f"Gender: {patient.get_gender_display() if patient.gender else 'Unknown'}",
            f"Location: {location or 'Unknown'}",
            f"Preferred language: {patient.get_preferred_language_display()}",
            f"Health conditions: {', '.join(map(str, patient.health_conditions or [])) or 'None recorded'}",
            f"Allergies: {', '.join(map(str, patient.allergies or [])) or 'None recorded'}",
        ]
        if patient.medical_notes:
            lines.append(f"Medical notes: {patient.medical_notes}")
        return "\n".join(lines)
