"""
Tests for Member 2's LLM Intelligence Module.
Uses pytest and pytest-asyncio to mock and verify structural extraction.
"""

import os
import json
import pytest
from unittest.mock import patch, AsyncMock

from app.llm.interpreter import interpret_operator_notes
from app.core.schemas import RawDirectiveDTO

# Helpers for mocking LLM string responses
def mock_llm_response(directives: list) -> str:
    return json.dumps({"directives": directives})

@pytest.fixture
def mock_generate_structured_extraction():
    with patch("app.llm.interpreter.generate_structured_extraction", new_callable=AsyncMock) as mock:
        yield mock

@pytest.mark.asyncio
async def test_solar_reduction_percentage(mock_generate_structured_extraction):
    # Test "reduced to 80%" vs "reduced by 80%"
    mock_generate_structured_extraction.return_value = mock_llm_response([
        {
            "note_index": 0,
            "directive_type": "solar_reduction",
            "raw_hours": [],
            "raw_numeric_param": 0.8,
            "confidence": 0.95
        },
        {
            "note_index": 1,
            "directive_type": "solar_reduction",
            "raw_hours": [],
            "raw_numeric_param": 0.2,
            "confidence": 0.95
        }
    ])
    
    notes = [
        "Solar is reduced to 80%",
        "Solar is reduced by 80%"
    ]
    results = await interpret_operator_notes(notes, "scenario_1")
    
    assert len(results) == 2
    assert results[0].directive_type == "solar_reduction"
    assert results[0].raw_numeric_param == 0.8
    assert results[1].directive_type == "solar_reduction"
    assert results[1].raw_numeric_param == 0.2

@pytest.mark.asyncio
async def test_solar_reduction_fraction(mock_generate_structured_extraction):
    # Test "drop by one-fifth" -> remaining 0.8
    mock_generate_structured_extraction.return_value = mock_llm_response([{
        "note_index": 0,
        "directive_type": "solar_reduction",
        "raw_hours": [],
        "raw_numeric_param": 0.8,
        "confidence": 0.95
    }])
    
    results = await interpret_operator_notes(["Solar drops by one-fifth"], "scenario_frac")
    assert results[0].raw_numeric_param == 0.8

@pytest.mark.asyncio
async def test_minimum_battery_reserve(mock_generate_structured_extraction):
    mock_generate_structured_extraction.return_value = mock_llm_response([{
        "note_index": 0,
        "directive_type": "minimum_battery_reserve",
        "raw_hours": [],
        "raw_numeric_param": 100.5,
        "confidence": 0.99
    }])
    
    results = await interpret_operator_notes(["Reserve must be at least 100.5 kWh"], "scenario_batt")
    assert results[0].directive_type == "minimum_battery_reserve"
    assert results[0].raw_numeric_param == 100.5

@pytest.mark.asyncio
async def test_time_handling_and_windows(mock_generate_structured_extraction):
    # Test 12-hour format ("1 PM to 3 PM") and 24-hour ("13:00 to 15:00") -> [13, 14]
    mock_generate_structured_extraction.return_value = mock_llm_response([
        {
            "note_index": 0,
            "directive_type": "no_charge_window",
            "raw_hours": [13, 14],
            "raw_numeric_param": 0.0,
            "confidence": 0.99
        },
        {
            "note_index": 1,
            "directive_type": "no_discharge_window",
            "raw_hours": [13, 14],
            "raw_numeric_param": 0.0,
            "confidence": 0.99
        }
    ])
    
    notes = [
        "Do not charge from 1 PM to 3 PM",
        "No discharge between 13:00 and 15:00"
    ]
    results = await interpret_operator_notes(notes, "scenario_time")
    
    assert results[0].raw_hours == [13, 14]
    assert results[0].directive_type == "no_charge_window"
    assert results[1].raw_hours == [13, 14]
    assert results[1].directive_type == "no_discharge_window"

@pytest.mark.asyncio
async def test_max_grid_window(mock_generate_structured_extraction):
    mock_generate_structured_extraction.return_value = mock_llm_response([{
        "note_index": 0,
        "directive_type": "max_grid_window",
        "raw_hours": [18, 19, 20],
        "raw_numeric_param": 500.0,
        "confidence": 0.99
    }])
    
    results = await interpret_operator_notes(["Cap grid usage to 500 kW from 18:00 to 21:00"], "scenario_grid")
    assert results[0].directive_type == "max_grid_window"
    assert results[0].raw_numeric_param == 500.0

@pytest.mark.asyncio
async def test_no_op_distractors(mock_generate_structured_extraction):
    mock_generate_structured_extraction.return_value = mock_llm_response([{
        "note_index": 0,
        "directive_type": "no_op",
        "raw_hours": [],
        "raw_numeric_param": 0.0,
        "confidence": 1.0
    }])
    
    results = await interpret_operator_notes(["The cafeteria is serving pizza today."], "scenario_distractor")
    assert results[0].directive_type == "no_op"

@pytest.mark.asyncio
async def test_multiple_notes_indexing(mock_generate_structured_extraction):
    mock_generate_structured_extraction.return_value = mock_llm_response([
        {"note_index": 0, "directive_type": "solar_reduction", "raw_hours": [], "raw_numeric_param": 0.5, "confidence": 0.9},
        {"note_index": 1, "directive_type": "no_op", "raw_hours": [], "raw_numeric_param": 0.0, "confidence": 0.9},
        {"note_index": 2, "directive_type": "minimum_battery_reserve", "raw_hours": [], "raw_numeric_param": 200.0, "confidence": 0.9}
    ])
    
    notes = ["Solar halved", "Weather is nice", "Keep 200 kWh"]
    results = await interpret_operator_notes(notes, "scenario_multi")
    
    assert len(results) == 3
    assert results[0].note_index == 0
    assert results[1].note_index == 1
    assert results[2].note_index == 2

@pytest.mark.asyncio
async def test_malformed_llm_output(mock_generate_structured_extraction):
    # Test that invalid JSON correctly raises a ValueError
    mock_generate_structured_extraction.return_value = "This is not JSON"
    
    with pytest.raises(ValueError) as exc:
        await interpret_operator_notes(["Valid note"], "scenario_err1")
    assert "LLM returned malformed JSON" in str(exc.value)

    # Test that missing required fields (schema mismatch) correctly raises a ValueError
    mock_generate_structured_extraction.return_value = json.dumps({"directives": [{"wrong_key": 1}]})
    
    with pytest.raises(ValueError) as exc:
        await interpret_operator_notes(["Valid note"], "scenario_err2")
    assert "LLM returned an invalid structure" in str(exc.value)

@pytest.mark.asyncio
async def test_real_api_smoke_test():
    """
    Optional manual smoke test to verify real API communication.
    Will be skipped automatically if GROQ_API_KEY is not set.
    """
    if not os.environ.get("GROQ_API_KEY"):
        pytest.skip("GROQ_API_KEY not set in environment.")
        
    notes = [
        "Reduce solar generation to 20% from 1 PM to 3 PM.",
        "The cafeteria will be busy."
    ]
    
    results = await interpret_operator_notes(notes, "smoke_test")
    
    assert len(results) == 2
    
    # Sort results by note_index to ensure deterministic asserting
    results.sort(key=lambda r: r.note_index)
    
    assert results[0].directive_type == "solar_reduction"
    assert results[0].raw_numeric_param == 0.2
    assert results[0].raw_hours == [13, 14]
    
    assert results[1].directive_type == "no_op"
