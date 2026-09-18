from typing import List, Dict, Any
from app.models import DirectiveInterpretationEntry, BatteryConfig

ALLOWED_DIRECTIVES = {
    "solar_reduction",
    "minimum_battery_reserve",
    "no_charge_window",
    "no_discharge_window",
    "max_grid_window",
    "no_op"
}

def validate_and_sanitize_directives(
    entries: List[DirectiveInterpretationEntry],
    note_count: int,
    battery: BatteryConfig
) -> List[DirectiveInterpretationEntry]:
    """
    Validates LLM interpreted directives against GridWise Section 08 guardrails.
    Returns sanitized directive entries.
    """
    if len(entries) != note_count:
        # Fallback to default no_op for missing entries
        sanitized = []
        for i in range(note_count):
            matching = [e for e in entries if e.note_index == i]
            if matching:
                sanitized.append(matching[0])
            else:
                sanitized.append(DirectiveInterpretationEntry(
                    note_index=i,
                    applies=False,
                    directive_type="no_op",
                    structured_adjustment=None,
                    explanation="No directive extracted; defaulted to no_op."
                ))
        entries = sanitized

    # Sort entries by note_index
    entries.sort(key=lambda x: x.note_index)

    sanitized_entries = []
    for idx, entry in enumerate(entries):
        entry.note_index = idx  # Enforce exact 0..N-1 ordering
        
        if entry.directive_type not in ALLOWED_DIRECTIVES:
            # Unsupported type -> convert to no_op
            sanitized_entries.append(DirectiveInterpretationEntry(
                note_index=idx,
                applies=False,
                directive_type="no_op",
                structured_adjustment=None,
                explanation="Unsupported directive type; converted to no_op."
            ))
            continue

        if entry.directive_type == "no_op":
            entry.applies = False
            entry.structured_adjustment = None
            sanitized_entries.append(entry)
            continue

        # Non no_op must have applies = True
        entry.applies = True
        adj = entry.structured_adjustment or {}

        # Validate hours array
        raw_hours = adj.get("hours", [])
        clean_hours = []
        for h in raw_hours:
            try:
                h_int = int(h)
                if 0 <= h_int <= 23 and h_int not in clean_hours:
                    clean_hours.append(h_int)
            except (ValueError, TypeError):
                pass
        clean_hours.sort()
        adj["hours"] = clean_hours

        # Type-specific checks
        if entry.directive_type == "solar_reduction":
            factor = float(adj.get("factor", 1.0))
            adj["factor"] = max(0.0, min(1.0, factor))

        elif entry.directive_type == "minimum_battery_reserve":
            min_kwh = float(adj.get("minimum_energy_kwh", battery.minimum_energy_kwh))
            adj["minimum_energy_kwh"] = max(0.0, min(battery.capacity_kwh, min_kwh))

        elif entry.directive_type == "max_grid_window":
            max_grid = float(adj.get("max_grid_kwh", 1e9))
            adj["max_grid_kwh"] = max(0.0, max_grid)

        entry.structured_adjustment = adj
        sanitized_entries.append(entry)

    return sanitized_entries
