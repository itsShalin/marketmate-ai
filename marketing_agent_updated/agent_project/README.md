# Marketing assistant: agent layer

Four agents (Planner, Analyst, Evaluator, Reporter) over one shared state. Only the Analyst uses tools.

## Setup (Windows PowerShell)
    python -m venv .venv
    .venv\Scripts\activate
    pip install -r requirements.txt
    copy .env.example .env          # then fill in the three Meterless values

## Test in three steps
1. No key, no backend (tests the orchestration and the revision loop):
       $env:MOCK_LLM="true"; $env:SAMPLE_MODE="true"; python run_demo.py
2. Mock backend + mock model (tests the HTTP tools):
       # terminal 1
       python mock_server.py
       # terminal 2
       $env:MOCK_LLM="true"; python run_demo.py
   Try $env:MOCK_SCENARIO="conflict" or "sparse" in terminal 1 before starting the server.
3. Real Nemotron via Meterless (remove MOCK_LLM): python run_demo.py

## Files
- marketing_agent/state.py         shared-state schema + final output schema (the JSON the frontend gets)
- marketing_agent/prompts.py       the four system prompts
- marketing_agent/orchestrator.py  run loop, retries, rule checks, fallbacks; entry point run_agent()
- marketing_agent/llm.py           Meterless/Nemotron client, retries, JSON repair
- marketing_agent/tools.py         the four Analyst tools (backend endpoints) + sample fallback
- marketing_agent/mock_*.py        sample data and canned model replies
- mock_server.py                   stand-in backend (stdlib only)
- logs/run_<id>.json               full agent log for every run (created automatically)

## Backend integration
Start the HTTP service (port 8001):
    uvicorn service:app --host 0.0.0.0 --port 8001
- `POST /run`  body: {"business_id": "biz_001", "request": "...", "sample_mode": false}  -> FinalOutput JSON (see state.py)
- `GET /health`
- The agent fetches data itself from BACKEND_BASE_URL: GET /api/business/{id}, /products, /inventory, /engagement
  (same routes as mock_server.py). The backend's /api/agent/run only needs to forward {business_id, request} to POST /run.
- Always returns HTTP 200; check the `status` field ("error" means the run failed safely).
