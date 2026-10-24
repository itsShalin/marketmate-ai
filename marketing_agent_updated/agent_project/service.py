"""HTTP wrapper around run_agent() so the Node backend can call the agent.
Start:  uvicorn service:app --host 0.0.0.0 --port 8001
"""
from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel

from marketing_agent.orchestrator import run_agent

app = FastAPI(title="MarketMate AI agent service")


class RunRequest(BaseModel):
    business_id: str
    request: str
    sample_mode: Optional[bool] = None   # true = skip the backend, use built-in sample data


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/run")
def run(body: RunRequest):
    # plain `def` so FastAPI runs this blocking call in a worker thread (a run can take up to RUN_TIMEOUT_S)
    return run_agent(body.business_id, body.request, body.sample_mode).model_dump()
