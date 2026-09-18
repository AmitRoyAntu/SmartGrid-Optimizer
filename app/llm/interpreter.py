"""
Interpreter service for LLM Intelligence Module.
Parses natural language operator notes into structured directives.
"""

import json
from typing import List

from app.llm.client import generate_structured_extraction
from app.llm.prompts import SYSTEM_PROMPT, FEW_SHOT_EXAMPLES
from app.core.schemas import RawDirectiveDTO

# Combine the system prompt with the few-shot examples
_FINAL_SYSTEM_PROMPT = SYSTEM_PROMPT + "\n\n### FEW-SHOT EXAMPLES ###\n" + json.dumps(FEW_SHOT_EXAMPLES, indent=2)

async def interpret_operator_notes(
    notes: List[str],
    scenario_id: str
) -> List[RawDirectiveDTO]:
    """
    Interprets 1-3 operator notes into raw structured directive objects.
    
    Args:
        notes: A list of natural language operator notes.
        scenario_id: The identifier for the current scenario.
        
    Returns:
        A list of RawDirectiveDTO objects.
    """
    if not notes:
        return []
        
    # Build structured user input preserving original indices
    structured_notes = [
        {"note_index": i, "text": note} 
        for i, note in enumerate(notes)
    ]
    user_input_json = json.dumps(structured_notes)
    
    try:
        # Call the Groq LLM client
        raw_json_response = await generate_structured_extraction(
            system_prompt=_FINAL_SYSTEM_PROMPT,
            user_input=user_input_json
        )
    except Exception as e:
        # Prevent obscure stack traces by wrapping connection/timeout errors clearly
        raise RuntimeError(f"Failed to communicate with LLM for scenario {scenario_id}: {str(e)}") from e
        
    try:
        # Parse the JSON returned by the LLM
        parsed_response = json.loads(raw_json_response)
        
        # Extract the directives array as specified in the prompt output format
        directives_data = parsed_response.get("directives", [])
        
        # Convert raw dicts into RawDirectiveDTO objects
        results = []
        for item in directives_data:
            # Delegate structural validation to Pydantic
            dto = RawDirectiveDTO(**item)
            results.append(dto)
            
        return results
        
    except json.JSONDecodeError as e:
        # Handle malformed JSON safely
        raise ValueError(f"LLM returned malformed JSON for scenario {scenario_id}: {raw_json_response}") from e
    except Exception as e:
        # Handle schema mismatch (e.g. Pydantic validation errors)
        raise ValueError(f"LLM returned an invalid structure for scenario {scenario_id}: {str(e)}") from e
