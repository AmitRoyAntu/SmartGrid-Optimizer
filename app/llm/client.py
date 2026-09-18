"""
Groq API client for the LLM interpretation module.
Handles API communication, timeouts, and retries.
"""

import os
import asyncio
from typing import Optional
from groq import AsyncGroq, APIConnectionError, APITimeoutError, RateLimitError

# Constants for latency and reliability management
DEFAULT_TIMEOUT = float(os.environ.get("LLM_TIMEOUT_SEC", 8.0))
MAX_RETRIES = 2
DEFAULT_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")

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
        base_url = os.environ.get("GROQ_BASE_URL")
        if base_url:
            base_url = base_url.removesuffix("/openai/v1").removesuffix("/")
        _client = AsyncGroq(
            api_key=api_key,
            base_url=base_url or None,
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
        except RateLimitError as e:
            if attempt == MAX_RETRIES:
                raise RuntimeError(f"Groq API failed after {MAX_RETRIES + 1} attempts: {str(e)}") from e
            wait_time = 2.5
            err_msg = str(e)
            if "try again in " in err_msg:
                try:
                    sec_str = err_msg.split("try again in ")[1].split("s")[0]
                    wait_time = float(sec_str) + 0.5
                except Exception:
                    wait_time = 2.5
            await asyncio.sleep(wait_time)
        except (APIConnectionError, APITimeoutError) as e:
            if attempt == MAX_RETRIES:
                raise RuntimeError(f"Groq API failed after {MAX_RETRIES + 1} attempts: {str(e)}") from e
            await asyncio.sleep(0.5)
