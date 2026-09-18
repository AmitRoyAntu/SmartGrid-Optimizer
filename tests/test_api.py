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
    data = response.json()
    assert data["detail"] == "Request validation failed"
    assert "errors" in data
    # Ensure no internal stack trace leaked
    assert "Traceback" not in response.text


def test_optimize_energy_with_mocked_llm(monkeypatch):
    """
    Test complete pipeline with active LLM directives extracted.
    Verifies LLM -> Guardrails -> Optimizer -> Replayer workflow.
    """
    mock_llm_json = json.dumps({
        "directives": [
            {
                "note_index": 0,
                "directive_type": "solar_reduction",
                "raw_hours": [13, 14],
                "raw_numeric_param": 0.2,
                "explanation": "Solar reduction to 20%",
                "confidence": 0.95
            },
            {
                "note_index": 1,
                "directive_type": "no_charge_window",
                "raw_hours": [14, 15],
                "raw_numeric_param": None,
                "explanation": "No charging",
                "confidence": 0.9
            }
        ]
    })

    async def mock_extraction(*args, **kwargs):
        return mock_llm_json

    monkeypatch.setattr(
        "app.llm.interpreter.generate_structured_extraction",
        mock_extraction
    )

    payloads_path = Path(__file__).parent / "sample_payloads.json"
    with open(payloads_path) as f:
        scenario = json.load(f)["sample_scenarios"][0]

    scenario["operator_notes"] = [
        "Solar output will drop to 20% from 1 PM to 3 PM.",
        "Do not charge the battery between 2 PM and 4 PM."
    ]

    response = client.post("/optimize-energy", json=scenario)
    assert response.status_code == 200
    res = response.json()

    assert len(res["directive_interpretation"]) == 2
    d0 = res["directive_interpretation"][0]
    assert d0["applies"] is True
    assert d0["directive_type"] == "solar_reduction"
    assert d0["structured_adjustment"] == {"hours": [13, 14], "factor": 0.2}

    d1 = res["directive_interpretation"][1]
    assert d1["applies"] is True
    assert d1["directive_type"] == "no_charge_window"
    assert d1["structured_adjustment"] == {"hours": [14, 15]}

    # Verify optimizer respected no-charge window for hours 14, 15
    for item in res["hourly_plan"]:
        if item["hour"] in [14, 15]:
            assert item["battery_action"] != "charge"
            assert item["battery_kwh"] == 0.0 or item["battery_action"] == "discharge"


def test_optimize_energy_llm_failure_resilience(monkeypatch):
    """
    Test resilient fallback when LLM API call fails (timeout or missing key).
    Endpoint must NOT crash with HTTP 500; must fall back to no_op and return valid schedule.
    """
    async def mock_failed_call(*args, **kwargs):
        raise RuntimeError("Groq connection timeout after 5.0s")

    monkeypatch.setattr(
        "app.llm.interpreter.generate_structured_extraction",
        mock_failed_call
    )

    payloads_path = Path(__file__).parent / "sample_payloads.json"
    with open(payloads_path) as f:
        scenario = json.load(f)["sample_scenarios"][0]

    response = client.post("/optimize-energy", json=scenario)
    assert response.status_code == 200
    res = response.json()

    # All directives should be gracefully marked no_op
    for d in res["directive_interpretation"]:
        assert d["applies"] is False
        assert d["directive_type"] == "no_op"
        assert d["structured_adjustment"] is None

    # Complete 24-hour schedule still validly generated
    assert len(res["hourly_plan"]) == 24
    assert res["total_cost_bdt"] > 0

