"""
Guardrails module: Deterministic validation & normalization of LLM directives.

This module ensures that raw, potentially messy LLM output is transformed into
safe, valid directive interpretations that can be safely consumed by the optimizer.
"""

from .validator import validate_and_guardrail_directives

__all__ = ["validate_and_guardrail_directives"]
