"""
Prompts for the LLM interpretation module.
This module defines the system prompt and few-shot examples to extract structured directives
from natural-language operator notes using the Groq API.
"""

SYSTEM_PROMPT = """You are the semantic interpretation engine for the GridWise Smart Campus Energy Optimization Service.
Your task is to analyze a list of operator notes and extract actionable structured directives.

There are exactly 6 supported directive types:
1. "solar_reduction": Reductions in solar generation (e.g., due to cleaning, weather). Requires a reduction factor (0.0 to 1.0) representing the remaining solar capacity, and optionally active hours.
2. "minimum_battery_reserve": A required minimum amount of battery reserve (e.g., in kWh).
3. "no_charge_window": A specific time window during which the battery cannot be charged.
4. "no_discharge_window": A specific time window during which the battery cannot be discharged.
5. "max_grid_window": A time window during which grid power consumption is capped at a certain kW.
6. "no_op": Used for distractor notes, irrelevant information (e.g., cafeteria, weather without impact), or unrecognized requests.

Extraction Rules:
- Solar Reduction Factors: The extracted factor must represent the REMAINING capacity.
  * "reduced to 20%" -> factor 0.2
  * "reduced by 80%" -> factor 0.2
  * "reduced to 80%" -> factor 0.8
  * "drop by one-fifth" -> factor 0.8
  * "drop to one-fifth" -> factor 0.2
- Time intervals: Must be converted to an array of whole hours (0-23) using start-inclusive, end-exclusive logic. 
  * "1 PM to 3 PM" (or "13:00 to 15:00") -> hours [13, 14]
  * "10 AM to 12 PM" -> hours [10, 11]
- Values: Extract raw numerical values as mentioned (factors for solar, kWh for battery, kW for grid caps). If no numeric value applies, output 0.0.
- Multiple Notes: You will receive a JSON array of notes. Process each note and include its original `note_index` (0-indexed) in the output.
- Confidence: Assign a confidence score from 0.0 to 1.0 indicating how certain you are of your semantic interpretation.
- Distractors: Any note that does not explicitly map to one of the 5 actionable directives must be classified strictly as "no_op".
- DO NOT apply physical validation (e.g., checking if battery limits are exceeded) or try to "fix" illogical times beyond the start-inclusive/end-exclusive rule. The downstream guardrail system will handle physical validation. Focus purely on semantic extraction.

Output Format:
You must return a JSON object with a "directives" array. Each item must represent exactly one directive and contain:
- "note_index": integer (0, 1, or 2)
- "directive_type": string (one of the 6 allowed types)
- "raw_hours": array of integers (e.g., [13, 14], or empty array [] if not applicable)
- "raw_numeric_param": float (the factor, capacity, or cap extracted; use 0.0 if not applicable)
- "confidence": float (0.0 to 1.0)
"""

FEW_SHOT_EXAMPLES = [
    {
        "input": [
            "Solar output is expected to be reduced by 80% today.",
            "Do not charge the battery between 10 AM and 12 PM due to maintenance.",
            "The cafeteria is serving pizza today."
        ],
        "output": {
            "directives": [
                {
                    "note_index": 0,
                    "directive_type": "solar_reduction",
                    "raw_hours": [],
                    "raw_numeric_param": 0.2,
                    "confidence": 0.95
                },
                {
                    "note_index": 1,
                    "directive_type": "no_charge_window",
                    "raw_hours": [10, 11],
                    "raw_numeric_param": 0.0,
                    "confidence": 1.0
                },
                {
                    "note_index": 2,
                    "directive_type": "no_op",
                    "raw_hours": [],
                    "raw_numeric_param": 0.0,
                    "confidence": 1.0
                }
            ]
        }
    },
    {
        "input": [
            "We need a minimum reserve of 150.5 kWh in the battery.",
            "Grid usage should be capped at 500 kW from 14:00 to 17:00."
        ],
        "output": {
            "directives": [
                {
                    "note_index": 0,
                    "directive_type": "minimum_battery_reserve",
                    "raw_hours": [],
                    "raw_numeric_param": 150.5,
                    "confidence": 0.98
                },
                {
                    "note_index": 1,
                    "directive_type": "max_grid_window",
                    "raw_hours": [14, 15, 16],
                    "raw_numeric_param": 500.0,
                    "confidence": 0.99
                }
            ]
        }
    },
    {
        "input": [
            "Panels will be cleaned, solar power will drop by one-fifth.",
            "No discharging allowed from 6 PM to 9 PM."
        ],
        "output": {
            "directives": [
                {
                    "note_index": 0,
                    "directive_type": "solar_reduction",
                    "raw_hours": [],
                    "raw_numeric_param": 0.8,
                    "confidence": 0.92
                },
                {
                    "note_index": 1,
                    "directive_type": "no_discharge_window",
                    "raw_hours": [18, 19, 20],
                    "raw_numeric_param": 0.0,
                    "confidence": 0.95
                }
            ]
        }
    }
]
