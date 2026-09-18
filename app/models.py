from typing import List, Optional, Literal, Dict, Any, Union
from pydantic import BaseModel, Field

class HourEntry(BaseModel):
    hour: int = Field(..., ge=0, le=23, description="Hour index from 0 to 23")
    demand_kwh: float = Field(..., ge=0, description="Campus demand in kWh")
    solar_kwh: float = Field(..., ge=0, description="Base forecast solar energy in kWh")
    tariff_bdt_per_kwh: float = Field(..., ge=0, description="Grid tariff in BDT per kWh")

class BatteryConfig(BaseModel):
    capacity_kwh: float = Field(..., gt=0, description="Total battery storage capacity in kWh")
    initial_energy_kwh: float = Field(..., ge=0, description="Energy in battery at start of hour 0")
    minimum_energy_kwh: float = Field(..., ge=0, description="Base minimum allowable battery reserve in kWh")
    max_charge_kwh_per_hour: float = Field(..., ge=0, description="Maximum charge rate in kWh/hour")
    max_discharge_kwh_per_hour: float = Field(..., ge=0, description="Maximum discharge rate in kWh/hour")

class OptimizeEnergyRequest(BaseModel):
    scenario_id: str = Field(..., description="Unique scenario identifier")
    operator_notes: List[str] = Field(..., min_length=1, max_length=3, description="1 to 3 natural language notes")
    hours: List[HourEntry] = Field(..., min_length=24, max_length=24, description="Exactly 24 hourly records")
    battery: BatteryConfig = Field(..., description="Battery parameters")

DirectiveTypeEnum = Literal[
    "solar_reduction",
    "minimum_battery_reserve",
    "no_charge_window",
    "no_discharge_window",
    "max_grid_window",
    "no_op"
]

BatteryActionEnum = Literal["charge", "discharge", "idle"]

class DirectiveInterpretationEntry(BaseModel):
    note_index: int = Field(..., ge=0, description="Zero-based index of corresponding operator note")
    applies: bool = Field(..., description="True if directive applies to today's schedule, false for no_op")
    directive_type: DirectiveTypeEnum = Field(..., description="Supported directive type or no_op")
    structured_adjustment: Optional[Dict[str, Any]] = Field(
        None,
        description="Structured adjustment object or null for no_op"
    )
    explanation: str = Field(..., description="Short explanation of directive interpretation")

class HourlyPlanEntry(BaseModel):
    hour: int = Field(..., ge=0, le=23, description="Hour index from 0 to 23")
    grid_kwh: float = Field(..., ge=0, description="Grid energy imported in kWh")
    solar_used_kwh: float = Field(..., ge=0, description="Solar energy consumed in kWh")
    battery_action: BatteryActionEnum = Field(..., description="Battery state: charge, discharge, or idle")
    battery_kwh: float = Field(..., ge=0, description="Magnitude of battery charge/discharge in kWh")
    battery_energy_after_kwh: float = Field(..., ge=0, description="Battery state of charge at end of hour in kWh")

class OptimizeEnergyResponse(BaseModel):
    scenario_id: str = Field(..., description="Echoes request scenario_id")
    directive_interpretation: List[DirectiveInterpretationEntry] = Field(..., description="Parsed directives per note")
    hourly_plan: List[HourlyPlanEntry] = Field(..., min_length=24, max_length=24, description="24-hour optimal schedule")
    total_grid_kwh: float = Field(..., ge=0, description="Sum of grid_kwh across all 24 hours")
    total_cost_bdt: float = Field(..., ge=0, description="Total grid electricity cost in BDT")
    peak_grid_kwh: float = Field(..., ge=0, description="Peak hourly grid_kwh")
    plan_summary: str = Field(..., description="Concise human-readable explanation of optimization plan")

class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
