"""
Groq API client for the LLM interpretation module.
Handles API communication, timeouts, and retries.
"""

import os
import asyncio
from typing import Optional
from groq import AsyncGroq, APIConnectionError, APITimeoutError, RateLimitError

# Constants for latency and reliability management
# Targeting p95 <= 5s. A 2.5s timeout allows for one retry within the 5s budget.
DEFAULT_TIMEOUT = 2.5
MAX_RETRIES = 1
DEFAULT_MODEL = "openai/gpt-oss-20b"

# Lazy-loaded client to avoid failing on import if env var is missing
_client: Optional[AsyncGroq] = None

def get_client() -> AsyncGroq:
    """
    Returns a configured AsyncGroq client instance.
    Raises ValueError if GROQ_API_KEY is not set.
    """
    global _client
    if _client is None:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable is missing")
        _client = AsyncGroq(
            api_key=api_key,
            timeout=DEFAULT_TIMEOUT,
            max_retries=0  # Retries are handled manually to strictly control overall latency
        )
    return _client

async def generate_structured_extraction(
    system_prompt: str,
    user_input: str,
    model: str = DEFAULT_MODEL
) -> str:
    """
    Calls the Groq API to extract structured JSON from the user input based on the system prompt.
    
    Args:
        system_prompt: The detailed system prompt with extraction rules.
        user_input: The JSON-serialized array of operator notes.
        model: The Groq model to use. Defaults to openai/gpt-oss-20b for low latency.
        
    Returns:
        The raw JSON string returned by the LLM.
        
    Raises:
        RuntimeError: If all retries are exhausted or a transient error persists.
        Exception: Passes through non-transient API errors (e.g., Auth errors).
    """
    client = get_client()
    
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = await client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_input}
                ],
                model=model,
                response_format={"type": "json_object"},
                temperature=0.0, # Ensures deterministic structured extraction
            )
            return response.choices[0].message.content
        except (APIConnectionError, APITimeoutError, RateLimitError) as e:
            if attempt == MAX_RETRIES:
                raise RuntimeError(f"Groq API failed after {MAX_RETRIES + 1} attempts: {str(e)}") from e
            # Lightweight backoff (0.5s) for transient errors to preserve overall latency target
            await asyncio.sleep(0.5)
