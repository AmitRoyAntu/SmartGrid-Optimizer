"""
End-to-End API and Integration Tests (Hour 3).
Tests HTTP contracts for GET /health and POST /optimize-energy.
"""

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_endpoint():
    """Verify GET /health returns 200 and {'status': 'ok'}."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_optimize_energy_end_to_end():
    """Verify POST /optimize-energy with canonical scenario from sample_payloads.json."""
    payloads_path = Path(__file__).parent / "sample_payloads.json"
    with open(payloads_path) as f:
        data = json.load(f)

    scenario = data["sample_scenarios"][0]
    response = client.post("/optimize-energy", json=scenario)

    assert response.status_code == 200
    res_json = response.json()

    # Verify top-level keys required by Problem Statement Section 10.1
    required_keys = [
        "scenario_id",
        "directive_interpretation",
        "hourly_plan",
        "total_grid_kwh",
        "total_cost_bdt",
        "peak_grid_kwh",
        "plan_summary",
    ]
    for key in required_keys:
        assert key in res_json, f"Missing required key '{key}' in response"

    assert res_json["scenario_id"] == scenario["scenario_id"]
    assert len(res_json["hourly_plan"]) == 24
    assert len(res_json["directive_interpretation"]) == len(scenario["operator_notes"])

    # Verify each hour in hourly_plan has required Section 10.3 keys
    for hour_item in res_json["hourly_plan"]:
        assert "hour" in hour_item
        assert "grid_kwh" in hour_item
        assert "solar_used_kwh" in hour_item
        assert hour_item["battery_action"] in ["charge", "discharge", "idle"]
        assert "battery_kwh" in hour_item
        assert "battery_energy_after_kwh" in hour_item


def test_invalid_json_returns_422():
    """Malformed request should be safely rejected with 422 Unprocessable Entity."""
    response = client.post("/optimize-energy", json={"invalid": "payload"})
    assert response.status_code == 422
