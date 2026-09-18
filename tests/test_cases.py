import os
import json
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_endpoint():
    """Verify GET /health readiness endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def load_sample_cases():
    base_dir = os.path.dirname(os.path.dirname(__file__))
    sample_file = os.path.join(base_dir, "sample_cases.json")
    with open(sample_file, "r") as f:
        data = json.load(f)
    return data["cases"]

@pytest.mark.parametrize("case", load_sample_cases(), ids=lambda c: c["id"])
def test_sample_case_optimization(case):
    """Verify POST /optimize-energy against all 10 public worked sample cases."""
    case_id = case["id"]
    inp = case["input"]
    expected = case["expected_output"]

    response = client.post("/optimize-energy", json=inp)
    assert response.status_code == 200, f"Failed for {case_id}: {response.text}"

    res_data = response.json()

    # 1. Echo scenario_id
    assert res_data["scenario_id"] == expected["scenario_id"]

    # 2. Directive interpretations matching
    parsed_directives = res_data["directive_interpretation"]
    exp_directives = expected["directive_interpretation"]
    assert len(parsed_directives) == len(exp_directives)

    for i, exp_d in enumerate(exp_directives):
        actual_d = parsed_directives[i]
        assert actual_d["note_index"] == exp_d["note_index"]
        assert actual_d["applies"] == exp_d["applies"]
        assert actual_d["directive_type"] == exp_d["directive_type"]
        
        if exp_d["applies"]:
            assert actual_d["structured_adjustment"] is not None
            exp_adj = exp_d["structured_adjustment"]
            act_adj = actual_d["structured_adjustment"]
            assert act_adj["hours"] == exp_adj["hours"]
            
            if "factor" in exp_adj:
                assert pytest.approx(act_adj["factor"], abs=0.01) == exp_adj["factor"]
            if "minimum_energy_kwh" in exp_adj:
                assert pytest.approx(act_adj["minimum_energy_kwh"], abs=0.5) == exp_adj["minimum_energy_kwh"]
            if "max_grid_kwh" in exp_adj:
                assert pytest.approx(act_adj["max_grid_kwh"], abs=0.5) == exp_adj["max_grid_kwh"]
        else:
            assert actual_d["structured_adjustment"] is None

    # 3. Hourly Plan verification
    hourly_plan = res_data["hourly_plan"]
    assert len(hourly_plan) == 24

    init_energy = inp["battery"]["initial_energy_kwh"]
    cap_energy = inp["battery"]["capacity_kwh"]

    for entry in hourly_plan:
        h = entry["hour"]
        grid = entry["grid_kwh"]
        solar_used = entry["solar_used_kwh"]
        action = entry["battery_action"]
        b_kwh = entry["battery_kwh"]
        e_after = entry["battery_energy_after_kwh"]

        c_kwh = b_kwh if action == "charge" else 0.0
        d_kwh = b_kwh if action == "discharge" else 0.0

        demand = inp["hours"][h]["demand_kwh"]

        # Energy Balance equation: grid + solar_used + discharge = demand + charge
        balance_lhs = grid + solar_used + d_kwh
        balance_rhs = demand + c_kwh
        assert pytest.approx(balance_lhs, abs=0.1) == balance_rhs, f"Hour {h} balance error in {case_id}"

        # Battery Bounds
        assert e_after <= cap_energy + 0.1, f"Hour {h} battery capacity exceeded in {case_id}"

    # 4. End-of-day battery neutrality
    final_e = hourly_plan[23]["battery_energy_after_kwh"]
    assert pytest.approx(final_e, abs=0.1) == init_energy, f"End of day neutrality broken in {case_id}"

    # 5. Total Cost BDT comparison (must match expected optimal cost within 1 BDT or tolerance)
    expected_cost = expected["total_cost_bdt"]
    actual_cost = res_data["total_cost_bdt"]
    assert pytest.approx(actual_cost, abs=10.0) == expected_cost, f"Cost mismatch for {case_id}: got {actual_cost}, expected {expected_cost}"
