import numpy as np
from scipy.optimize import linprog
from typing import List, Tuple
from app.models import (
    HourEntry,
    BatteryConfig,
    DirectiveInterpretationEntry,
    HourlyPlanEntry,
    OptimizeEnergyResponse
)

def solve_energy_optimization(
    scenario_id: str,
    hours: List[HourEntry],
    battery: BatteryConfig,
    directives: List[DirectiveInterpretationEntry]
) -> Tuple[List[HourlyPlanEntry], float, float, float, str]:
    """
    Solves 24-hour energy optimization LP using SciPy HiGHS solver.
    """
    num_hours = 24
    
    # 1. Process Directives onto Hourly Modifiers
    effective_solar = [h.solar_kwh for h in hours]
    effective_min_battery = [battery.minimum_energy_kwh] * num_hours
    max_charge = [battery.max_charge_kwh_per_hour] * num_hours
    max_discharge = [battery.max_discharge_kwh_per_hour] * num_hours
    max_grid = [float('inf')] * num_hours

    for d in directives:
        if not d.applies or not d.structured_adjustment:
            continue
        
        target_hours = d.structured_adjustment.get("hours", [])
        
        if d.directive_type == "solar_reduction":
            factor = float(d.structured_adjustment.get("factor", 1.0))
            for h_idx in target_hours:
                if 0 <= h_idx < num_hours:
                    effective_solar[h_idx] = hours[h_idx].solar_kwh * factor

        elif d.directive_type == "minimum_battery_reserve":
            req_min = float(d.structured_adjustment.get("minimum_energy_kwh", battery.minimum_energy_kwh))
            for h_idx in target_hours:
                if 0 <= h_idx < num_hours:
                    effective_min_battery[h_idx] = max(effective_min_battery[h_idx], req_min)

        elif d.directive_type == "no_charge_window":
            for h_idx in target_hours:
                if 0 <= h_idx < num_hours:
                    max_charge[h_idx] = 0.0

        elif d.directive_type == "no_discharge_window":
            for h_idx in target_hours:
                if 0 <= h_idx < num_hours:
                    max_discharge[h_idx] = 0.0

        elif d.directive_type == "max_grid_window":
            req_grid_max = float(d.structured_adjustment.get("max_grid_kwh", float('inf')))
            for h_idx in target_hours:
                if 0 <= h_idx < num_hours:
                    max_grid[h_idx] = min(max_grid[h_idx], req_grid_max)

    # 2. Formulate LP
    # Variables per hour h:
    # 0: g_h (grid_kwh)
    # 1: s_h (solar_used_kwh)
    # 2: c_h (battery_charge_kwh)
    # 3: d_h (battery_discharge_kwh)
    # 4: E_h (battery_energy_after_kwh)
    
    num_vars = num_hours * 5
    c_obj = np.zeros(num_vars)
    bounds = []
    
    for h in range(num_hours):
        c_obj[5*h + 0] = hours[h].tariff_bdt_per_kwh  # g_h cost
        c_obj[5*h + 1] = 0.0                          # s_h
        c_obj[5*h + 2] = 0.0                          # c_h
        c_obj[5*h + 3] = 0.0                          # d_h
        c_obj[5*h + 4] = 0.0                          # E_h
        
        # Bounds:
        # g_h: [0, max_grid[h]]
        bounds.append((0.0, max_grid[h] if max_grid[h] != float('inf') else None))
        # s_h: [0, effective_solar[h]]
        bounds.append((0.0, max(0.0, effective_solar[h])))
        # c_h: [0, max_charge[h]]
        bounds.append((0.0, max_charge[h]))
        # d_h: [0, max_discharge[h]]
        bounds.append((0.0, max_discharge[h]))
        # E_h: [effective_min_battery[h], capacity_kwh]
        bounds.append((effective_min_battery[h], battery.capacity_kwh))

    # Equality Constraints A_eq * x = b_eq
    # 1. Energy Balance: g_h + s_h + d_h - c_h = demand_h  (24 equations)
    # 2. Battery Dynamics: E_0 - c_0 + d_0 = E_init (h=0)
    #                      E_h - E_{h-1} - c_h + d_h = 0 (h > 0)  (24 equations)
    # 3. End-of-day Neutrality: E_23 = E_init  (1 equation)
    
    num_eq = 24 + 24 + 1
    A_eq = np.zeros((num_eq, num_vars))
    b_eq = np.zeros(num_eq)
    
    eq_row = 0
    # 1. Energy balance
    for h in range(num_hours):
        A_eq[eq_row, 5*h + 0] = 1.0   # g_h
        A_eq[eq_row, 5*h + 1] = 1.0   # s_h
        A_eq[eq_row, 5*h + 3] = 1.0   # d_h
        A_eq[eq_row, 5*h + 2] = -1.0  # -c_h
        b_eq[eq_row] = hours[h].demand_kwh
        eq_row += 1

    # 2. Battery dynamics
    # h = 0: E_0 - c_0 + d_0 = E_init
    A_eq[eq_row, 5*0 + 4] = 1.0   # E_0
    A_eq[eq_row, 5*0 + 2] = -1.0  # -c_0
    A_eq[eq_row, 5*0 + 3] = 1.0   # +d_0
    b_eq[eq_row] = battery.initial_energy_kwh
    eq_row += 1

    for h in range(1, num_hours):
        A_eq[eq_row, 5*h + 4] = 1.0       # E_h
        A_eq[eq_row, 5*(h-1) + 4] = -1.0  # -E_{h-1}
        A_eq[eq_row, 5*h + 2] = -1.0      # -c_h
        A_eq[eq_row, 5*h + 3] = 1.0       # +d_h
        b_eq[eq_row] = 0.0
        eq_row += 1

    # 3. End-of-day Neutrality
    A_eq[eq_row, 5*23 + 4] = 1.0  # E_23
    b_eq[eq_row] = battery.initial_energy_kwh
    eq_row += 1

    # Solve LP
    res = linprog(c_obj, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method='highs')
    
    if not res.success:
        raise ValueError(f"Optimization solver failed: {res.message}")

    x = res.x
    hourly_plan = []
    total_grid_kwh = 0.0
    total_cost_bdt = 0.0
    peak_grid_kwh = 0.0

    for h in range(num_hours):
        g_val = round(float(x[5*h + 0]), 2)
        s_val = round(float(x[5*h + 1]), 2)
        c_val = float(x[5*h + 2])
        d_val = float(x[5*h + 3])
        e_val = round(float(x[5*h + 4]), 2)

        if c_val > 0.01:
            action = "charge"
            b_val = round(c_val, 2)
        elif d_val > 0.01:
            action = "discharge"
            b_val = round(d_val, 2)
        else:
            action = "idle"
            b_val = 0.0

        hourly_plan.append(HourlyPlanEntry(
            hour=h,
            grid_kwh=g_val,
            solar_used_kwh=s_val,
            battery_action=action,
            battery_kwh=b_val,
            battery_energy_after_kwh=e_val
        ))

        total_grid_kwh += g_val
        total_cost_bdt += g_val * hours[h].tariff_bdt_per_kwh
        if g_val > peak_grid_kwh:
            peak_grid_kwh = g_val

    total_grid_kwh = round(total_grid_kwh, 2)
    total_cost_bdt = round(total_cost_bdt, 2)
    peak_grid_kwh = round(peak_grid_kwh, 2)

    plan_summary = (
        f"Optimized 24-hour schedule using SciPy HiGHS solver. "
        f"Total Grid Import: {total_grid_kwh} kWh, Peak Import: {peak_grid_kwh} kWh, Total Cost: {total_cost_bdt} BDT. "
        f"Battery end-of-day level restored to initial state ({battery.initial_energy_kwh} kWh)."
    )

    return hourly_plan, total_grid_kwh, total_cost_bdt, peak_grid_kwh, plan_summary
