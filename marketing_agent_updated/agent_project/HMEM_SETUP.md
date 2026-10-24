# H-MEM integration: what changed and how to run it

This project uses the actual Meterless H-MEM TypeScript reference, vendored under
`vendor/hmem/reference`, through a Python subprocess adapter. It does not call an
invented H-MEM API or require a running Nightshift instance for memory operations.
Nemotron/model requests still use your existing Meterless configuration in llm.py.

## 1. Install and start (Windows PowerShell)

Install Node.js **24 or newer**, then reopen PowerShell. No Docker, GPU or npm
install is needed for the memory engine. The code runs using Node's
`--experimental-transform-types` support.

From `agent_project`:

```powershell
node --version
python -m pip install -r requirements.txt
```

Copy **your existing .env** into this folder. The downloadable archive deliberately
contains `.env.example`, not your API keys. Do not overwrite your working keys.
Append this to .env:

```dotenv
HMEM_ENABLED=true
```

Optional: `HMEM_DIR=D:/marketmate-memory` sets an absolute persistent storage path.
The default is `agent_project/data/hmem`. Keep it when restarting/updating the app.
`HMEM_NODE` can point to an absolute node.exe path if Node is not on PATH.

For the first local wiring test, set `MOCK_LLM=true` **inside .env**. Your existing
load_dotenv(override=True) means .env wins over shell environment variables.
For real model testing, set `MOCK_LLM=false` and retain your verified Meterless /
Nemotron settings. Memory does not configure or validate the provider connection.

Start the service:

```powershell
python -m uvicorn service:app --host 127.0.0.1 --port 8001
```

## 2. Prove memory survives a restart

In another terminal from agent_project:

```powershell
python memory_demo.py seed
```

Stop the service with Ctrl+C and start it again using the command above. Then:

```powershell
python memory_demo.py run --sample
python memory_demo.py inspect
```

`seed` records the owner preference: avoid discounts and use a premium friendly tone.
`run` calls the existing /run endpoint; --sample uses sample backend data only.
`inspect` prints persisted memory plus its append-only create/read ledger.
Check `logs/run_<id>.json` for `memory_context`, `memory_trace`, and `hmem:recall`.
The same remembered preference is passed to Planner, Analyst and Evaluator.
Mocks prove retrieval and prompt injection; only a real-model run demonstrates
Nemotron actually follows that preference. The original canned mock text does not
adapt its captions to memory.

With the real backend available, omit --sample. A real backend brand_voice is
captured into working memory after the run; sample/fallback data is not saved.
Explicit owner preferences for that key take precedence over backend defaults.

## 3. Backend integration

POST /run still returns the original FinalOutput shape. See UPDATE_NOTES.md for stricter unresolved-review status handling. Both `businessId` and
`business_id` are accepted; the response shape is unchanged.

Use POST /memory when the owner explicitly saves a reusable preference:

```json
{
  "business_id": "biz_001",
  "key": "promotion_policy",
  "content": "Avoid discounts. Use a premium, friendly tone."
}
```

Use a stable key (e.g. brand_voice, promotion_policy, target_audience). Sending the
same key and content again is idempotent. A correction with the same key replaces
the active preference, retaining the old record with a supersededBy link and
conflict audit entries. Other keys remain active. This is an explicit owner
update policy, not automatic inference about whether two sentences contradict.

GET /memory?business_id=biz_001 returns that business's records and ledger.
POST /memory/feedback takes:

```json
{"business_id":"biz_001","memory_id":"mem-1","kind":"wrong"}
```

Supported feedback: helpful (+0.05 confidence), not_helpful (-0.03), wrong (-0.20
and review tag). Review-tagged records are not injected by the application.
Use /docs for interactive request examples. These endpoints inherit the original
local service's lack of authentication; keep it bound to localhost. A public
backend must authenticate the owner and derive business_id from that identity.

## 4. Changed files

| File | Purpose |
|---|---|
| marketing_agent/memory.py | Python adapter; per-business hashed storage paths; cross-worker file lock |
| marketing_agent/hmem_bridge.ts | Calls H-MEM add/query/feedback; keyed updates and active preference recall |
| vendor/hmem/ | Unmodified Meterless engine source, spec, conformance suite, Apache license |
| marketing_agent/orchestrator.py | Recall before planning; pass context to three roles; capture real brand_voice |
| marketing_agent/state.py | Internal memory_context and memory_trace; no FinalOutput changes |
| marketing_agent/prompts.py | Memory usage rules; current backend facts and current request take precedence |
| service.py | Memory endpoints and businessId compatibility |
| requirements.txt | Adds filelock |
| .env.example / .gitignore | Memory settings; exclude secrets and generated state |
| memory_demo.py / tests/test_memory.py | Restart demo and integration tests |

## 5. How it works and practical limits

- Each business gets its own H-MEM state.json and ledger.jsonl, so relationships,
  retrieval and memory IDs are isolated. A file lock serializes operations.
- H-MEM supplies tier fields, provenance, relationship links, canonical hybrid
  ranking, grouped prompt reinjection and audited reads/writes/feedback.
- The application also includes up to five active business preferences even when
  a short request has little keyword overlap. This inclusion rule is distinct
  from H-MEM's canonical relevance score; memory_trace labels that policy.
- Explicit owner preferences are long_term; real backend brand_voice is working.
  The existing RunState remains volatile per-run context. This application does
  not automatically promote a model draft into an owner preference or mine every
  free-text request. Save a reusable preference explicitly through POST /memory.
- Never store stock as lasting memory: current stock/engagement are fetched through
  the existing backend tools. The evaluator's existing stock checks remain active.
- A missing/broken Node engine makes a /run response include a memory caveat;
  explicit memory writes return an error. There is no silent in-memory substitute.
- This is a hackathon reference integration, using the upstream deterministic hash
  embedder and local JSON persistence. It is not a semantic embedding model or a
  crash-safe production database. Do not delete state files to resolve corruption;
  restore from a backup. Cross-machine shared storage is outside this adapter.
- Upstream dream/sleep/conflict services are included and tested by conformance,
  but automatic dreaming, consolidation and their HTTP/UI workflows are not enabled.
- H-MEM needs no Meterless/NVIDIA key for storage. Your model path still needs the
  working credentials/configuration you already use. A memory test is not proof
  of a successful live Nemotron call.

## 6. Verification

Run the upstream conformance checks against the vendored reference:

```powershell
node --experimental-transform-types vendor/hmem/conformance/runner.ts
```

Run the Python integration tests (the tests force mocked model calls):

```powershell
python -m pip install httpx
python -m unittest discover -s tests
```

Tests cover restart persistence, generic-request recall, business isolation/path
safety, deduplication, owner corrections and source precedence, feedback,
concurrent writes, HTTP request compatibility, all three prompt inputs, and
unavailable-node degradation. No API keys or live backend are required.
