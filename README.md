# GridWise — Smart Campus Energy Optimization System

> **BUP CSE Fest 2026 · Hackathon · Online Preliminary Round**  
> LLM-Assisted Operator Directive Interpretation & Smart Campus 24-Hour Energy Scheduling API.

---

## ⚡ System Architecture

GridWise is an end-to-end smart energy management service built on FastAPI, Google Gemini LLM, and SciPy HiGHS Linear Programming Solver.

```
┌────────────────────────┐      ┌───────────────────────────┐
│  Energy Data & Notes   │ ───► │  LLM Directive Interpreter│
└────────────────────────┘      └───────────────────────────┘
                                              │
                                              ▼
┌────────────────────────┐      ┌───────────────────────────┐
│  API Output & Web UI   │ ◄─── │  SciPy HiGHS LP Solver    │
└────────────────────────┘      └───────────────────────────┘
                                 (Satisfies Energy Balance,
                                  Battery Bounds & Directives)
```

1. **LLM Interpreter Layer**: Takes 1–3 natural-language operator notes and extracts structured directives (`solar_reduction`, `minimum_battery_reserve`, `no_charge_window`, `no_discharge_window`, `max_grid_window`, `no_op`). Uses **Google Gemini 2.5 Flash** with standard JSON schema enforcement and includes a zero-dependency deterministic fallback parser for offline testing.
2. **Deterministic Guardrails**: Validates note indexing (0..N-1), time window bounds (0..23 ascending), numeric ranges (solar factors in `[0..1]`, non-negative reserves/caps), and `applies` semantics.
3. **Mathematical Optimizer**: Formulates and solves a 24-hour Linear Program using SciPy's HiGHS solver to minimize total grid electricity cost $\sum_{h=0}^{23} \text{grid\_kwh}[h] \cdot \text{tariff}[h]$.
4. **Interactive Dashboard**: High-tech web dashboard displaying 24-hour energy balance, battery state-of-charge (SOC) curves, tariff graphs, and directive analysis.

---

## 🚀 Quickstart & Reproduction Guide

### Prerequisites
- Python 3.10+
- (Optional) Docker & Docker Compose

### 1. Local Setup
```bash
# Clone repository
git clone https://github.com/your-team/gridwise.git
cd gridwise

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Environment Configuration
(Optional) Set your Google Gemini API key to enable live LLM interpretation. If omitted, GridWise automatically utilizes its deterministic fallback parser.
```bash
export GEMINI_API_KEY="your-google-gemini-api-key"
# On Windows PowerShell: $env:GEMINI_API_KEY="your-google-gemini-api-key"
```

### 3. Run API Server & Dashboard
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8050
```
- **API Base URL**: `http://localhost:8050`
- **Interactive Web UI**: `http://localhost:8050/`
- **OpenAPI Docs**: `http://localhost:8050/docs`

---

## 🧪 Testing & Verification

Run the automated PyTest suite to verify health readiness and test all 10 public sample scenarios:
```bash
python -m pytest tests/test_cases.py -v
```

---

## 📡 API Endpoint Reference

### 1. Health Readiness
- **Endpoint**: `GET /health`
- **Response**:
```json
{
  "status": "ok"
}
```
- **cURL Command**:
```bash
curl http://localhost:8050/health
```

### 2. Energy Optimization
- **Endpoint**: `POST /optimize-energy`
- **Content-Type**: `application/json`
- **Sample cURL Request**:
```bash
curl -X POST "http://localhost:8050/optimize-energy" \
  -H "Content-Type: application/json" \
  -d '{
    "scenario_id": "SAMPLE-01",
    "operator_notes": [
      "Facilities will wash the rooftop solar panels from noon until 2 PM. During cleaning, usable solar should be treated as roughly 25% of the forecast.",
      "The sports office moved next month registration deadline."
    ],
    "hours": [
      {"hour": 0, "demand_kwh": 90, "solar_kwh": 0, "tariff_bdt_per_kwh": 6},
      {"hour": 1, "demand_kwh": 85, "solar_kwh": 0, "tariff_bdt_per_kwh": 6},
      {"hour": 2, "demand_kwh": 80, "solar_kwh": 0, "tariff_bdt_per_kwh": 5},
      {"hour": 3, "demand_kwh": 80, "solar_kwh": 0, "tariff_bdt_per_kwh": 5},
      {"hour": 4, "demand_kwh": 85, "solar_kwh": 0, "tariff_bdt_per_kwh": 5},
      {"hour": 5, "demand_kwh": 95, "solar_kwh": 0, "tariff_bdt_per_kwh": 6},
      {"hour": 6, "demand_kwh": 110, "solar_kwh": 5, "tariff_bdt_per_kwh": 8},
      {"hour": 7, "demand_kwh": 130, "solar_kwh": 20, "tariff_bdt_per_kwh": 10},
      {"hour": 8, "demand_kwh": 150, "solar_kwh": 50, "tariff_bdt_per_kwh": 12},
      {"hour": 9, "demand_kwh": 165, "solar_kwh": 90, "tariff_bdt_per_kwh": 14},
      {"hour": 10, "demand_kwh": 175, "solar_kwh": 130, "tariff_bdt_per_kwh": 16},
      {"hour": 11, "demand_kwh": 180, "solar_kwh": 160, "tariff_bdt_per_kwh": 16},
      {"hour": 12, "demand_kwh": 185, "solar_kwh": 180, "tariff_bdt_per_kwh": 15},
      {"hour": 13, "demand_kwh": 180, "solar_kwh": 170, "tariff_bdt_per_kwh": 14},
      {"hour": 14, "demand_kwh": 170, "solar_kwh": 140, "tariff_bdt_per_kwh": 13},
      {"hour": 15, "demand_kwh": 165, "solar_kwh": 90, "tariff_bdt_per_kwh": 14},
      {"hour": 16, "demand_kwh": 170, "solar_kwh": 45, "tariff_bdt_per_kwh": 18},
      {"hour": 17, "demand_kwh": 185, "solar_kwh": 10, "tariff_bdt_per_kwh": 22},
      {"hour": 18, "demand_kwh": 205, "solar_kwh": 0, "tariff_bdt_per_kwh": 28},
      {"hour": 19, "demand_kwh": 215, "solar_kwh": 0, "tariff_bdt_per_kwh": 30},
      {"hour": 20, "demand_kwh": 205, "solar_kwh": 0, "tariff_bdt_per_kwh": 26},
      {"hour": 21, "demand_kwh": 175, "solar_kwh": 0, "tariff_bdt_per_kwh": 18},
      {"hour": 22, "demand_kwh": 135, "solar_kwh": 0, "tariff_bdt_per_kwh": 10},
      {"hour": 23, "demand_kwh": 105, "solar_kwh": 0, "tariff_bdt_per_kwh": 7}
    ],
    "battery": {
      "capacity_kwh": 220,
      "initial_energy_kwh": 110,
      "minimum_energy_kwh": 40,
      "max_charge_kwh_per_hour": 50,
      "max_discharge_kwh_per_hour": 50
    }
  }'
```

---

## 🐳 Docker Fallback Deployment

### Build Docker Image
```bash
docker build -t gridwise-app:latest .
```

### Run Docker Container
```bash
docker run -d -p 8050:8050 -e GEMINI_API_KEY="your-api-key" --name gridwise_service gridwise-app:latest
```

### Verify Container Health
```bash
curl http://localhost:8050/health
```

---

## 📜 License & Compliance
Built for **BUP CSE Fest 2026 Hackathon Preliminary**. Complies with all schema, guardrail, optimization, and submission rules defined in the official problem statement and evaluation rubric.
