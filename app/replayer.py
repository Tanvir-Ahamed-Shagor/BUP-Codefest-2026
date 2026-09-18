from typing import List, Tuple
from app.models import HourEntry, HourlyPlanEntry

def recalculate_and_verify_plan(
    hourly_plan: List[HourlyPlanEntry],
    hours: List[HourEntry]
) -> Tuple[float, float, float]:
    """
    Recalculates total_grid_kwh, total_cost_bdt, and peak_grid_kwh
    directly from hourly_plan and hourly tariffs to guarantee perfect accuracy.
    """
    total_grid = 0.0
    total_cost = 0.0
    peak_grid = 0.0

    tariff_map = {h.hour: h.tariff_bdt_per_kwh for h in hours}

    for entry in hourly_plan:
        g = entry.grid_kwh
        tariff = tariff_map.get(entry.hour, 0.0)
        
        total_grid += g
        total_cost += g * tariff
        if g > peak_grid:
            peak_grid = g

    return round(total_grid, 2), round(total_cost, 2), round(peak_grid, 2)
