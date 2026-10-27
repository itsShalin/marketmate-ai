"""One place that talks to Nemotron through Meterless (OpenAI-compatible API).
Handles: timeouts, retries with backoff, <think> stripping, JSON extraction, and JSON repair retries."""
import json
import os
import re
import time

from . import budget
from dotenv import load_dotenv

load_dotenv(override=False)

LLM_TIMEOUT_S = float(os.getenv("LLM_TIMEOUT_S", "90"))
LLM_RETRIES = int(os.getenv("LLM_RETRIES", "2"))          # extra attempts on network/5xx errors
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "4000"))
JSON_REPAIRS = 2                                            # extra attempts when the reply is not valid JSON
MOCK_LLM = os.getenv("MOCK_LLM", "false").lower() == "true"


class LLMError(Exception):
    """Raised when the model cannot give us a usable answer. Callers decide on a fallback."""


_client = None


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI
        for key in ("METERLESS_BASE_URL", "METERLESS_API_KEY"):
            if not os.environ.get(key):
                raise LLMError(f"{key} is missing from .env")
        _client = OpenAI(base_url=os.environ["METERLESS_BASE_URL"],
                         api_key=os.environ["METERLESS_API_KEY"],
                         default_headers={"meterless-app": "marketmate", "meterless-scope": "user"},
                         timeout=LLM_TIMEOUT_S, max_retries=0)   # we do our own retries
    return _client

def _find_receipt(obj, keys=("routed_model", "receipt_id")):
    found = {}
    stack = [obj]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            for k, v in cur.items():
                if k in keys and k not in found:
                    found[k] = v
                elif isinstance(v, (dict, list)):
                    stack.append(v)
        elif isinstance(cur, list):
            stack.extend(cur)
    return found

def _chat(messages, temperature):
    from openai import APIConnectionError, APIStatusError, APITimeoutError, RateLimitError
    client, last = _get_client(), None
    for attempt in range(LLM_RETRIES + 1):
        try:
            r = client.chat.completions.create(model=os.getenv("NEMOTRON_MODEL", "meterless/fast"), messages=messages,
                                               temperature=temperature, max_tokens=LLM_MAX_TOKENS,
                                               timeout=budget.timeout(LLM_TIMEOUT_S))
            budget.remaining()
            receipt = _find_receipt(r.model_dump())
            receipt["requested_model"] = os.getenv("NEMOTRON_MODEL", "meterless/fast")
            receipt["model"] = r.model            # model name the SDK reports, as a fallback
            return (r.choices[0].message.content or ""), receipt
        except (APITimeoutError, APIConnectionError, RateLimitError) as e:
            last = e
        except APIStatusError as e:
            if e.status_code < 500:                  # 4xx (bad key, bad model id): retrying will not help
                raise LLMError(f"model request rejected ({e.status_code}): {str(e)[:150]}")
            last = e
        if attempt < LLM_RETRIES:
            budget.pause(2 ** attempt)                     # 1s, 2s, 4s
    raise LLMError(f"model unavailable after {LLM_RETRIES + 1} attempts: {last}")


def extract_json(text: str) -> dict:
    # Some providers omit the opening reasoning tag.
    closes = list(re.finditer(r"</think\s*>", text, flags=re.I))
    if closes:
        text = text[closes[-1].end():]
    elif re.search(r"<think\b[^>]*>", text, flags=re.I):
        raise ValueError("unfinished reasoning block; no final answer found")

    text = text.replace("```json", "").replace("```", "").strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object found in reply")

    result = json.loads(text[start:end + 1])
    if not isinstance(result, dict):
        raise ValueError("expected one JSON object")
    return result


def call_json(role, system, messages, validate, temperature=0.2, on_receipt=None):
    """Call the model and return (validated_object, raw_text).
    If the reply is not valid JSON or fails `validate`, tell the model what was wrong and retry."""
    prefix = os.getenv("SYSTEM_PREFIX", "").strip()
    msgs = [{"role": "system", "content": (prefix + "\n" + system).strip()}] + list(messages)
    last_err = None
    for _ in range(JSON_REPAIRS + 1):
        budget.remaining()
        if MOCK_LLM:
            from .mock_llm import respond
            text, receipt = respond(role, msgs), {}
        else:
            text, receipt = _chat(msgs, temperature)
        if receipt and on_receipt:
            on_receipt(role, receipt)
        try:
            return validate(extract_json(text)), text
        except ValueError as e:           # json errors and pydantic ValidationError both land here
            print(f"[{role}] validation failed: {str(e)[:500]}; reply length={len(text)}")
            if on_receipt:
                on_receipt(role, {"validation_error": str(e)[:500], "reply_chars": len(text)})
            last_err = e
            msgs += [{"role": "assistant", "content": text},
                     {"role": "user", "content": f"Your reply was invalid: {str(e)[:300]}. "
                                                 "Reply again with ONLY the corrected JSON object."}]
    raise LLMError(f"{role}: no valid JSON after {JSON_REPAIRS + 1} tries: {last_err}")
