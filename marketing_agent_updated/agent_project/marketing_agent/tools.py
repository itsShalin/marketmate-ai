"""Analyst tools. Each tool is one backend endpoint (which queries Zetaris).
Falls back to built-in sample data if the backend is down, so a run never hangs or crashes on data."""
import os
import time

import requests

from .mock_data import get_mock
from . import budget

BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", "http://localhost:8000").rstrip("/")
TOOL_TIMEOUT_S = float(os.getenv("TOOL_TIMEOUT_S", "5"))
TOOL_RETRIES = int(os.getenv("TOOL_RETRIES", "1"))

# tool name -> (data kind, endpoint suffix).  Keep in sync with the agreed API contract.
ENDPOINTS = {
    "get_business_profile": ("profile", ""),
    "get_products": ("products", "/products"),
    "get_inventory": ("inventory", "/inventory"),
    "get_engagement": ("engagement", "/engagement"),
}


def call_tool(name: str, business_id: str, sample_mode: bool) -> dict:
    """Returns {"source": "backend" | "sample" | "sample_fallback", "kind": ..., "data": ..., "error": optional}."""
    if name not in ENDPOINTS:
        raise ValueError(f"unknown tool '{name}'. Valid tools: {list(ENDPOINTS)}")
    budget.remaining()
    kind, suffix = ENDPOINTS[name]
    sample = get_mock(os.getenv("MOCK_SCENARIO", "normal"))[kind]
    if sample_mode:
        return {"source": "sample", "kind": kind, "data": sample}

    url = f"{BACKEND_BASE_URL}/api/business/{business_id}{suffix}"
    last = None
    for attempt in range(TOOL_RETRIES + 1):
        try:
            r = requests.get(url, timeout=budget.timeout(TOOL_TIMEOUT_S))
            budget.remaining()
            r.raise_for_status()
            return {"source": "backend", "kind": kind, "data": r.json()}
        except (requests.RequestException, ValueError) as e:
            last = e
            if attempt < TOOL_RETRIES:
                budget.pause(0.5 * (attempt + 1))
    return {"source": "sample_fallback", "kind": kind, "data": sample, "error": str(last)[:120]}
