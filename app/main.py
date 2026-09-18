import os
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.models import (
    OptimizeEnergyRequest,
    OptimizeEnergyResponse,
    HealthResponse
)
from app.llm_interpreter import interpret_operator_notes
from app.guardrails import validate_and_sanitize_directives
from app.optimizer import solve_energy_optimization
from app.replayer import recalculate_and_verify_plan

app = FastAPI(
    title="GridWise — Smart Campus Energy Optimization API",
    description="LLM-assisted operator directive interpretation and 24-hour battery/grid energy optimization service for BUP CSE Fest 2026 Hackathon.",
    version="2.0.0"
)

# Endpoint: GET /health
@app.get("/health", response_model=HealthResponse)
def get_health():
    """Readiness endpoint for the judging harness."""
    return HealthResponse(status="ok")

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    from fastapi.responses import Response
    return Response(status_code=204)

# Endpoint: POST /optimize-energy
@app.post("/optimize-energy", response_model=OptimizeEnergyResponse)
@app.post("/optimize-energy/", response_model=OptimizeEnergyResponse, include_in_schema=False)
def optimize_energy(req: OptimizeEnergyRequest):
    """
    Main GridWise endpoint:
    1. Interprets 1-3 operator notes using LLM / Guardrailed Interpreter.
    2. Validates & sanitizes directives deterministically.
    3. Solves 24-hour linear program to minimize total grid cost.
    4. Recalculates metrics and returns optimal hourly plan.
    """
    try:
        # 1. LLM Directive Interpretation
        raw_directives = interpret_operator_notes(req.operator_notes, req.battery)
        
        # 2. Guardrails & Sanitization
        sanitized_directives = validate_and_sanitize_directives(
            raw_directives,
            len(req.operator_notes),
            req.battery
        )

        # 3. Math Optimization
        hourly_plan, total_grid, total_cost, peak_grid, summary = solve_energy_optimization(
            req.scenario_id,
            req.hours,
            req.battery,
            sanitized_directives
        )

        # 4. Recalculate metrics for 100% verification
        ver_grid, ver_cost, ver_peak = recalculate_and_verify_plan(hourly_plan, req.hours)

        return OptimizeEnergyResponse(
            scenario_id=req.scenario_id,
            directive_interpretation=sanitized_directives,
            hourly_plan=hourly_plan,
            total_grid_kwh=ver_grid,
            total_cost_bdt=ver_cost,
            peak_grid_kwh=ver_peak,
            plan_summary=summary
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/optimize-energy", include_in_schema=False)
@app.get("/optimize-energy/", include_in_schema=False)
def get_optimize_energy_info():
    return {
        "message": "POST /optimize-energy requires an HTTP POST request with a scenario JSON payload.",
        "usage": "Use POST /optimize-energy, visit / for the interactive Web UI Dashboard, or visit /docs for API documentation."
    }


# Static Files for Web UI
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
def read_root():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "GridWise API is running. Visit /docs for OpenAPI documentation."}
