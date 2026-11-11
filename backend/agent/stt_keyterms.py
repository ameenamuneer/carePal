"""
Known words ("keyterms") for ElevenLabs Scribe speech recognition.

Scribe can be biased toward known words (names, medicines, places), which fixes
misheard names like 'ഹാറൂനിസ' → 'ഹാരൂൺ ഈസ'. The patient may speak any of the
app's languages, so every term is sent in all of their scripts (English,
Malayalam, Tamil, Hindi). Measured: keyterms in Latin script ALONE make Scribe
translate Malayalam speech into English; Latin plus native-script forms keep
each utterance in the language it was spoken in (Malayalam stays Malayalam,
English stays English, nothing drifts into Tamil/Hindi script). Conversion to
the other scripts is one Gemini Flash call, cached.
"""

import hashlib
import json
import logging

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

# App terms, plus whatever is derived from the patient's data.
STATIC_KEYTERMS = ["CarePal", "BP", "blood pressure", "blood sugar", "pulse"]
# Scribe limits: ≤1000 terms, each ≤50 characters and ≤5 words.
MAX_KEYTERMS = 1000
TRANSLITERATION_MODEL = "gemini-2.5-flash"
CACHE_SECONDS = 7 * 24 * 3600


def build_keyterms(patient) -> list:
    """Known words from the patient's data (Latin or any script), deduplicated."""
    from medications.models import Medication
    from patients.models import EmergencyContact
    from family.models import FamilyMember

    terms = list(STATIC_KEYTERMS)
    if patient:
        user = patient.user
        terms += [user.get_full_name(), user.first_name, user.last_name]
        terms += [patient.city, patient.state]
        terms += [patient.doctor_name, patient.doctor_clinic, patient.pharmacy_name]
        terms += [str(c) for c in patient.health_conditions or []]
        terms += [str(a) for a in patient.allergies or []]
        terms += list(Medication.objects.filter(patient=patient).values_list('medication_name', flat=True))
        terms += list(EmergencyContact.objects.filter(patient=patient).values_list('name', flat=True))
        for member in FamilyMember.objects.filter(patient=patient).select_related('user'):
            if member.user:
                terms += [member.user.get_full_name(), member.user.first_name]
        terms += [str(t) for t in patient.stt_keyterms or []]
    return _clean(terms)


def _clean(terms) -> list:
    seen, result = set(), []
    for term in terms:
        term = " ".join((term or "").split())
        if not term or len(term) > 50 or len(term.split()) > 5 or term.lower() in seen:
            continue
        seen.add(term.lower())
        result.append(term)
    return result[:MAX_KEYTERMS]


# Scripts every keyterm is sent in: code → (description for the model, letter check).
SCRIPTS = {
    "eng": ("English / Latin spelling", lambda ch: ch.isascii()),
    "mal": ("Malayalam script", lambda ch: "\u0d00" <= ch <= "\u0d7f"),
    "tam": ("Tamil script", lambda ch: "\u0b80" <= ch <= "\u0bff"),
    "hin": ("Hindi (Devanagari script)", lambda ch: "\u0900" <= ch <= "\u097f"),
}
# Each source term becomes up to len(SCRIPTS) keyterms; stay under Scribe's cap.
MAX_SOURCE_TERMS = MAX_KEYTERMS // len(SCRIPTS)


def _in_script(term: str, code: str) -> bool:
    letters = [ch for ch in term if ch.isalpha()]
    return bool(letters) and all(SCRIPTS[code][1](ch) for ch in letters)


def expand_scripts(terms: list) -> list:
    """
    Every term in all SCRIPTS (the original spelling is kept too). Blocking
    (network call); if the conversion fails, returns only the original terms
    that are in a native script plus their Latin ones — never Latin alone,
    which would make Scribe translate.
    """
    terms = terms[:MAX_SOURCE_TERMS]
    if not terms:
        return []
    key = "stt_keyterms_v2:" + hashlib.sha256(json.dumps(sorted(terms)).encode()).hexdigest()
    variants = cache.get(key)
    if variants is None:
        try:
            import os
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY") or getattr(settings, "GOOGLE_API_KEY", None))
            wanted = ", ".join(f'"{code}": {desc}' for code, (desc, _) in SCRIPTS.items())
            response = client.models.generate_content(
                model=TRANSLITERATION_MODEL,
                contents=json.dumps(terms, ensure_ascii=False),
                config=types.GenerateContentConfig(
                    system_instruction=(
                        "Transliterate each term (names, medicines, places, words) into each of these "
                        f"scripts: {wanted}. Write it the way a native speaker would spell it when "
                        "said aloud in conversation — phonetically, never translated (e.g. 'Meftal Forte' "
                        "→ Malayalam 'മെഫ്റ്റാൽ ഫോർട്ട്', 'BP' → Hindi 'बीपी'). For \"eng\", give the usual "
                        "English/Latin spelling. Return a JSON object mapping each script code to an "
                        "array of strings in the same order as the input."
                    ),
                    response_mime_type="application/json",
                    temperature=0,
                ),
            )
            data = json.loads(response.text)
            variants = {code: [str(t) for t in data.get(code, [])] for code in SCRIPTS}
            if any(len(v) != len(terms) for v in variants.values()):
                raise ValueError("transliteration returned the wrong number of terms")
            cache.set(key, variants, CACHE_SECONDS)
        except Exception as e:
            logger.warning(f"Keyterm transliteration failed; using only native-script terms: {e}")
            if not any(not _in_script(t, "eng") for t in terms):
                return []  # Latin-only keyterms would make Scribe translate
            return _clean(terms)
    expanded = list(terms)
    for code, forms in variants.items():
        expanded += [t for t in forms if _in_script(t, code)]
    return _clean(expanded)
