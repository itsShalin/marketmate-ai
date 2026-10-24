"""Start locally: uvicorn service:app --host 127.0.0.1 --port 8001"""
from typing import Optional, Literal
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, AliasChoices, ConfigDict
from marketing_agent.orchestrator import run_agent
from marketing_agent import memory

app = FastAPI(title="MarketMate AI agent service")

class RunRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    business_id: str = Field(min_length=1, max_length=200, validation_alias=AliasChoices('business_id', 'businessId'))
    request: str = Field(min_length=1, max_length=20000)
    sample_mode: Optional[bool] = None

class MemoryWrite(BaseModel):
    business_id: str = Field(min_length=1, max_length=200)
    key: str = Field(min_length=1, max_length=100)
    content: str = Field(min_length=1, max_length=2000)

class MemoryFeedback(BaseModel):
    business_id: str = Field(min_length=1, max_length=200)
    memory_id: str = Field(min_length=1, max_length=100)
    kind: Literal['helpful', 'not_helpful', 'wrong']


def memory_call(fn, *args, **kwargs):
    if not memory.enabled():
        raise HTTPException(503, 'H-MEM is disabled')
    try:
        return fn(*args, **kwargs)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    except memory.MemoryError as e:
        raise HTTPException(503, str(e)) from e

@app.get('/health')
def health():
    return {'status': 'ok', 'hmem_enabled': memory.enabled()}

@app.post('/run')
def run(body: RunRequest):
    return run_agent(body.business_id, body.request, body.sample_mode).model_dump()

@app.post('/memory')
def remember(body: MemoryWrite):
    return memory_call(memory.remember, body.business_id, body.key, body.content)

@app.get('/memory')
def inspect_memory(business_id: str):
    return memory_call(memory.invoke, business_id, 'inspect')

@app.post('/memory/feedback')
def feedback(body: MemoryFeedback):
    return memory_call(memory.invoke, body.business_id, 'feedback', memory_id=body.memory_id, kind=body.kind)
