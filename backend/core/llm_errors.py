"""Helpers for classifying upstream LLM provider failures."""

from __future__ import annotations

import re
from typing import Optional, Tuple


LlmErrorEnvelope = Tuple[int, str, str, str]


def classify_llm_error(exc: Exception) -> Optional[LlmErrorEnvelope]:
    message = str(exc).strip()
    lowered = message.lower()

    is_quota_error = (
        "resource_exhausted" in lowered
        or "quota exceeded" in lowered
        or "error code: 429" in lowered
        or "status': 'resource_exhausted'" in lowered
    )
    if not is_quota_error:
        return None

    retry_match = re.search(r"retry(?: in)?\s+([0-9]+(?:\.[0-9]+)?s)", message, re.IGNORECASE)
    retry_hint = (
        f" Retry after {retry_match.group(1)}."
        if retry_match
        else ""
    )
    detail = (
        "The configured LLM provider rejected the request because the current quota "
        "for this model is exhausted."
        f"{retry_hint} Set DEFAULT_MODEL or GEMINI_MODEL to a lower-cost model such as "
        "`gemini-2.5-flash`, or enable billing for the current provider."
    )
    return (
        429,
        "LLM_QUOTA_EXCEEDED",
        "LLM quota exceeded",
        detail,
    )
