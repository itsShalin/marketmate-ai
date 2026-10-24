"""One place that talks to Nemotron through Meterless (OpenAI-compatible API).
Handles: timeouts, retries with backoff, <think> stripping, JSON extraction, and JSON repair retries."""
import json
import os
import re
import time

from dotenv import load_dotenv

load_dotenv()

LLM_TIMEOUT_S = float(os.getenv("LLM_TIMEOUT_S", "45"))
LLM_RETRIES = int(os.getenv("LLM_RETRIES", "2"))          # extra attempts on network/5xx errors
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "1500"))
JSON_REPAIRS = 2                                            # extra attempts when the reply is not valid JSON
MOCK_LLM = os.getenv("MOCK_LLM", "false").lower() == "true"


class LLMError(Exception):
    """Raised when the model cannot give us a usable answer. Callers decide on a fallback."""


_client = None


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI
        for key in ("METERLESS_BASE_URL", "METERLESS_API_KEY", "NEMOTRON_MODEL"):
            if not os.environ.get(key):
                raise LLMError(f"{key} is missing from .env")
        _client = OpenAI(base_url=os.environ["METERLESS_BASE_URL"],
                         api_key=os.environ["METERLESS_API_KEY"],
                         timeout=LLM_TIMEOUT_S, max_retries=0)   # we do our own retries
    return _client


def _chat(messages, temperature):
    from openai import APIConnectionError, APIStatusError, APITimeoutError, RateLimitError
    client, last = _get_client(), None
    for attempt in range(LLM_RETRIES + 1):
        try:
            r = client.chat.completions.create(model=os.environ["NEMOTRON_MODEL"], messages=messages,
                                               temperature=temperature, max_tokens=LLM_MAX_TOKENS)
            return r.choices[0].message.content or ""
        except (APITimeoutError, APIConnectionError, RateLimitError) as e:
            last = e
        except APIStatusError as e:
            if e.status_code < 500:                  # 4xx (bad key, bad model id): retrying will not help
                raise LLMError(f"model request rejected ({e.status_code}): {str(e)[:150]}")
            last = e
        time.sleep(2 ** attempt)                     # 1s, 2s, 4s
    raise LLMError(f"model unavailable after {LLM_RETRIES + 1} attempts: {last}")


def extract_json(text: str) -> dict:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)   # some Nemotron versions emit reasoning
    text = text.replace("```json", "").replace("```", "").strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object found in reply")
    return json.loads(text[start:end + 1])


def call_json(role, system, messages, validate, temperature=0.2):
    """Call the model and return (validated_object, raw_text).
    If the reply is not valid JSON or fails `validate`, tell the model what was wrong and retry."""
    prefix = os.getenv("SYSTEM_PREFIX", "").strip()
    msgs = [{"role": "system", "content": (prefix + "\n" + system).strip()}] + list(messages)
    last_err = None
    for _ in range(JSON_REPAIRS + 1):
        if MOCK_LLM:
            from .mock_llm import respond
            text = respond(role, msgs)
        else:
            text = _chat(msgs, temperature)
        try:
            return validate(extract_json(text)), text
        except ValueError as e:                      # json errors and pydantic ValidationError both land here
            last_err = e
            msgs += [{"role": "assistant", "content": text},
                     {"role": "user", "content": f"Your reply was invalid: {str(e)[:300]}. "
                                                 "Reply again with ONLY the corrected JSON object."}]
    raise LLMError(f"{role}: no valid JSON after {JSON_REPAIRS + 1} tries: {last_err}")
