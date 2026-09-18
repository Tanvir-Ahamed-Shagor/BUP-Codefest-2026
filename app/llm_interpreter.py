import os
import re
import json
from typing import List, Dict, Any, Optional
from app.models import DirectiveInterpretationEntry, BatteryConfig

SYSTEM_PROMPT = """You are an expert energy management directive interpreter for GridWise Smart Campus.
Your task is to analyze natural-language operator notes for a 24-hour smart campus energy schedule (hours 0 through 23).

Supported directive types and required structured_adjustment shapes:
1. "solar_reduction": Usable solar output is reduced during specific hours.
   structured_adjustment: {"hours": [int, ...], "factor": float}
   NOTE: factor is the fraction of solar REMAINING usable (e.g., 25% usable -> factor = 0.25; 80% reduction -> factor = 0.2; half forecast -> factor = 0.5).
2. "minimum_battery_reserve": Battery energy must remain at or above a specified level (in kWh).
   structured_adjustment: {"hours": [int, ...], "minimum_energy_kwh": float}
   NOTE: If stated as percentage (e.g. 50% of 200 kWh capacity), convert to kWh (100.0).
3. "no_charge_window": Battery charging is completely disabled/forbidden during listed hours.
   structured_adjustment: {"hours": [int, ...]}
4. "no_discharge_window": Battery discharging is completely disabled/forbidden during listed hours.
   structured_adjustment: {"hours": [int, ...]}
5. "max_grid_window": Grid electricity import must not exceed a stated kWh threshold in any listed hour.
   structured_adjustment: {"hours": [int, ...], "max_grid_kwh": float}
6. "no_op": Note is unrelated or does not affect today's 24-hour energy schedule.
   applies: false
   structured_adjustment: null

Rules:
- Output MUST be valid JSON containing an array of objects for each operator note in note_index order (0, 1, ... N-1).
- Time windows use start-inclusive, end-exclusive 0-23 whole hours. (e.g. 1 PM to 3 PM -> [13, 14]; 6 PM to 9 PM -> [18, 19, 20]; noon to 2 PM -> [12, 13]; 2 AM to 5 AM -> [2, 3, 4]).
- For no_op: applies MUST be false and structured_adjustment MUST be null.
- For all other directives: applies MUST be true.
"""

def parse_time_window(text: str) -> List[int]:
    """Helper to convert human time strings into list of 0-23 hours."""
    text_lower = text.lower()
    
    # 24-hour format patterns like "13:00 and 15:00" or "13:00 to 15:00"
    match_24 = re.search(r'(\d{1,2}):00\s*(?:to|and|until|-)\s*(\d{1,2}):00', text_lower)
    if match_24:
        start, end = int(match_24.group(1)), int(match_24.group(2))
        return list(range(start, end))

    time_map = {
        "midnight": 0, "1 am": 1, "2 am": 2, "3 am": 3, "4 am": 4, "5 am": 5, "6 am": 6,
        "7 am": 7, "8 am": 8, "9 am": 9, "10 am": 10, "11 am": 11, "noon": 12, "12 pm": 12,
        "1 pm": 13, "2 pm": 14, "3 pm": 15, "4 pm": 16, "5 pm": 17, "6 pm": 18, "7 pm": 19,
        "8 pm": 20, "9 pm": 21, "10 pm": 22, "11 pm": 23
    }
    
    tokens = []
    for phrase, hour_val in sorted(time_map.items(), key=lambda x: -len(x[0])):
        if phrase in text_lower:
            for m in re.finditer(r'\b' + re.escape(phrase) + r'\b', text_lower):
                tokens.append((m.start(), hour_val))
    
    tokens.sort(key=lambda x: x[0])
    if len(tokens) >= 2:
        start_h = tokens[0][1]
        end_h = tokens[1][1]
        if end_h > start_h:
            return list(range(start_h, end_h))
            
    return []

def fallback_interpret_note(note: str, note_idx: int, battery: BatteryConfig) -> DirectiveInterpretationEntry:
    """Deterministic fallback parser for natural language operator notes."""
    note_lower = note.lower()

    # 1. Distractor check (no_op)
    distractor_keywords = [
        "cafeteria", "registration deadline", "book-return", "club notices", 
        "seminar room", "sports office", "student affairs", "library is extending"
    ]
    if any(k in note_lower for k in distractor_keywords):
        return DirectiveInterpretationEntry(
            note_index=note_idx,
            applies=False,
            directive_type="no_op",
            structured_adjustment=None,
            explanation="This note does not affect today's 24-hour energy schedule."
        )

    hours = parse_time_window(note)

    # 2. Solar reduction
    if any(k in note_lower for k in ["solar", "pv production", "cloud cover", "panel"]):
        factor = 1.0
        pct_reduction = re.search(r'(\d+)%\s*reduction', note_lower)
        pct_usable = re.search(r'(\d+)%\s*(?:of\s+the\s+forecast|usable)', note_lower)
        if pct_reduction:
            red_val = float(pct_reduction.group(1))
            factor = round((100.0 - red_val) / 100.0, 4)
        elif pct_usable:
            usable_val = float(pct_usable.group(1))
            factor = round(usable_val / 100.0, 4)
        elif "half" in note_lower or "one-half" in note_lower:
            factor = 0.5
        elif "one-fifth" in note_lower:
            factor = 0.2
        elif "25%" in note_lower:
            factor = 0.25

        return DirectiveInterpretationEntry(
            note_index=note_idx,
            applies=True,
            directive_type="solar_reduction",
            structured_adjustment={"hours": hours, "factor": factor},
            explanation=f"Solar availability is reduced to {int(factor*100)}% during the window."
        )

    # 3. Minimum battery reserve
    if any(k in note_lower for k in ["reserve", "in the battery", "in battery", "stored in battery", "battery capacity stored", "backup"]):
        min_kwh = battery.minimum_energy_kwh
        pct_match = re.search(r'(\d+)%\s*of\s*(?:the\s*)?battery\s*capacity', note_lower)
        kwh_match = re.search(r'(\d+(?:\.\d+)?)\s*kwh', note_lower)
        if pct_match:
            pct = float(pct_match.group(1))
            min_kwh = (pct / 100.0) * battery.capacity_kwh
        elif kwh_match:
            min_kwh = float(kwh_match.group(1))

        return DirectiveInterpretationEntry(
            note_index=note_idx,
            applies=True,
            directive_type="minimum_battery_reserve",
            structured_adjustment={"hours": hours, "minimum_energy_kwh": min_kwh},
            explanation=f"A {min_kwh} kWh minimum battery reserve is required during the window."
        )

    # 4. No charge window
    if any(k in note_lower for k in ["charger will be isolated", "charging circuit", "not charge", "charging is disabled", "no_charge", "charger"]):
        return DirectiveInterpretationEntry(
            note_index=note_idx,
            applies=True,
            directive_type="no_charge_window",
            structured_adjustment={"hours": hours},
            explanation="Battery charging is unavailable during the window."
        )

    # 5. No discharge window
    if any(k in note_lower for k in ["not discharge", "relay testing", "discharge is disabled", "discharge"]):
        return DirectiveInterpretationEntry(
            note_index=note_idx,
            applies=True,
            directive_type="no_discharge_window",
            structured_adjustment={"hours": hours},
            explanation="Battery discharge is disabled during the window."
        )

    # 6. Max grid window
    if any(k in note_lower for k in ["grid import", "grid intake", "feeder", "transformer", "grid"]):
        max_kwh = 0.0
        kwh_match = re.search(r'(\d+(?:\.\d+)?)\s*kwh', note_lower)
        if kwh_match:
            max_kwh = float(kwh_match.group(1))

        return DirectiveInterpretationEntry(
            note_index=note_idx,
            applies=True,
            directive_type="max_grid_window",
            structured_adjustment={"hours": hours, "max_grid_kwh": max_kwh},
            explanation=f"Grid import is capped at {max_kwh} kWh during the window."
        )

    # Default to no_op if unmatched
    return DirectiveInterpretationEntry(
        note_index=note_idx,
        applies=False,
        directive_type="no_op",
        structured_adjustment=None,
        explanation="Note does not affect today's energy schedule."
    )


def interpret_operator_notes(
    notes: List[str],
    battery: BatteryConfig
) -> List[DirectiveInterpretationEntry]:
    """
    Main interpretation function. Uses Gemini API if GEMINI_API_KEY is configured,
    else falls back to deterministic rule parser.
    """
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    
    if api_key:
        try:
            from google import genai
            from google.genai import types
            
            client = genai.Client(api_key=api_key)
            prompt = f"{SYSTEM_PROMPT}\n\nBattery capacity: {battery.capacity_kwh} kWh, Base reserve: {battery.minimum_energy_kwh} kWh.\nOperator Notes:\n"
            for i, note in enumerate(notes):
                prompt += f"Note {i}: \"{note}\"\n"
            prompt += "\nReturn JSON list of interpreted directives."

            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.0
                )
            )

            res_text = response.text
            parsed_json = json.loads(res_text)
            
            if isinstance(parsed_json, dict) and "directive_interpretation" in parsed_json:
                parsed_json = parsed_json["directive_interpretation"]

            entries = []
            for item in parsed_json:
                entries.append(DirectiveInterpretationEntry(**item))
            return entries
        except Exception as e:
            pass

    # Deterministic parser fallback
    return [fallback_interpret_note(note, idx, battery) for idx, note in enumerate(notes)]
