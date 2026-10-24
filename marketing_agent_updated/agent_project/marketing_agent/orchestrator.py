"""Runs Planner -> Analyst -> Evaluator (-> revise loop) -> Reporter over a shared RunState.
Every loop is bounded: model retries, JSON repairs, tool retries, tool steps, revision rounds, total run time."""
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from . import prompts
from .llm import LLMError, call_json
from .state import (FinalOutput, Message, Plan, ReporterOut, Recommendation, Review, RunState)
from .tools import ENDPOINTS, call_tool

MAX_REVISIONS = int(os.getenv("MAX_REVISIONS", "2"))
MAX_TOOL_STEPS = int(os.getenv("MAX_TOOL_STEPS", "6"))
RUN_TIMEOUT_S = float(os.getenv("RUN_TIMEOUT_S", "180"))
LOW_STOCK = 3
RANK = {"low": 0, "medium": 1, "high": 2}


class RunTimeout(Exception):
    pass


# ---------- helpers ----------
def log(state, agent, kind, content):
    state.log.append(Message(ts=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                             agent=agent, kind=kind, content=content))
    print(f"[{agent}:{kind}] {str(content)[:160]}")


def user_msg(payload):
    return {"role": "user", "content": json.dumps(payload, default=str)}


def check_deadline(state):
    if time.time() - state.started_at > RUN_TIMEOUT_S:
        raise RunTimeout(f"run exceeded {RUN_TIMEOUT_S:.0f}s")


def add_unique(items, text):
    if text not in items:
        items.append(text)


def rows(data):
    """Accept a plain list or {"items": [...]} so a small contract change does not break us."""
    if isinstance(data, dict):
        data = data.get("items", [])
    return [r for r in data if isinstance(r, dict)] if isinstance(data, list) else []


# ---------- 1. Planner ----------
def run_planner(state):
    try:
        plan, _ = call_json("planner", prompts.PLANNER,
                            [user_msg({"request": state.request, "business_id": state.business_id})],
                            Plan.model_validate)
    except LLMError as e:
        plan = Plan(data_needed=["profile", "products", "inventory", "engagement"],
                    success_criteria=["every draft cites data", "no out-of-stock promotion"],
                    assumptions=["Planner failed; default plan used"])
        add_unique(state.caveats, "Planner unavailable; default plan used")
        log(state, "planner", "fallback", str(e))
    state.plan = plan
    log(state, "planner", "plan", plan.model_dump())


# ---------- 2. Analyst (the only agent with tools) ----------
def _validate_step(d):
    action = d.get("action")
    if action == "call_tool":
        if d.get("tool") not in ENDPOINTS:
            raise ValueError(f"unknown tool {d.get('tool')!r}; valid: {list(ENDPOINTS)}")
        return {"action": "call_tool", "tool": d["tool"]}
    if action == "final":
        drafts = [Recommendation.model_validate(x) for x in d.get("drafts", [])]
        gaps = [str(g) for g in d.get("data_gaps", [])]
        if not drafts and not gaps:
            raise ValueError("final needs at least one draft or a data_gaps explanation")
        return {"action": "final", "drafts": drafts, "data_gaps": gaps}
    raise ValueError("action must be 'call_tool' or 'final'")


def run_analyst(state, feedback: Review | None = None):
    first = {"request": state.request, "plan": state.plan.model_dump(),
             "tool_results_so_far": state.tool_data,
             "previous_drafts": [d.model_dump() for d in state.drafts],
             "reviewer_feedback": feedback.model_dump() if feedback else None}
    messages = [user_msg(first)]

    for _ in range(MAX_TOOL_STEPS):
        check_deadline(state)
        step, raw = call_json("analyst", prompts.ANALYST, messages, _validate_step)
        messages.append({"role": "assistant", "content": raw})
        if step["action"] == "final":
            return _accept_final(state, step)

        name = step["tool"]
        kind = ENDPOINTS[name][0]
        log(state, "analyst", "tool_call", name)
        if kind in state.tool_data:                              # never fetch the same thing twice
            result = {"source": "cache", "kind": kind, "data": state.tool_data[kind]}
        else:
            result = call_tool(name, state.business_id, state.sample_mode)
            state.tool_data[kind] = result["data"]
            if result["source"] == "sample_fallback":
                add_unique(state.data_gaps, f"Backend unreachable for {kind}; sample data used")
                add_unique(state.caveats, "Backend fallback used")
        log(state, "analyst", "tool_result", {"tool": name, "source": result["source"]})
        messages.append(user_msg({"tool_result": {"tool": name, "source": result["source"], "data": result["data"]}}))

    # tool budget spent: force a final answer from what we have
    messages.append(user_msg({"instruction": "Tool budget used up. Reply now with action=final using only the data you have."}))
    step, _ = call_json("analyst", prompts.ANALYST, messages, _validate_step)
    if step["action"] != "final":
        raise LLMError("analyst did not finish within the tool budget")
    _accept_final(state, step)


def _accept_final(state, step):
    state.drafts = step["drafts"]
    for g in step["data_gaps"]:
        add_unique(state.data_gaps, g)
    log(state, "analyst", "draft", f"{len(state.drafts)} drafts, {len(step['data_gaps'])} data gaps")


# ---------- 3. Evaluator (LLM critic + deterministic rule checks against the raw data) ----------
def rule_checks(state):
    """Independent of the model: checks the drafts against the raw backend data."""
    issues = []
    inv = {r.get("product_id"): r for r in rows(state.tool_data.get("inventory", []))}
    products = rows(state.tool_data.get("products", []))
    for i, d in enumerate(state.drafts):
        if not d.evidence:
            issues.append(f"Draft {i}: no evidence cited")
        text = d.draft.lower()
        for p in products:
            name = str(p.get("name", "")).strip()
            if not name or name.lower() not in text:
                continue
            stock = inv.get(p.get("id"), {}).get("stock")
            if p.get("status") in ("discontinued", "inactive"):
                issues.append(f"Draft {i}: promotes '{name}' which is {p.get('status')}")
            if stock is None:
                if not d.warnings:
                    issues.append(f"Draft {i}: stock for '{name}' is unknown; add a warning")
            elif stock <= 0:
                issues.append(f"Draft {i}: promotes '{name}' which is out of stock (0 units)")
            elif stock <= LOW_STOCK and not d.warnings:
                issues.append(f"Draft {i}: '{name}' has only {stock} units; add a low-stock warning")
    return issues


def run_evaluator(state) -> Review:
    profile = state.tool_data.get("profile") or {}
    payload = {"plan": state.plan.model_dump(), "brand_voice": profile.get("brand_voice"),
               "drafts": [d.model_dump() for d in state.drafts], "data_gaps": state.data_gaps,
               "revision_round": state.revision_count}
    try:
        review, _ = call_json("evaluator", prompts.EVALUATOR, [user_msg(payload)], Review.model_validate, temperature=0.0)
    except LLMError as e:
        review = Review(verdict="pass", feedback="Model review unavailable; rule checks only")
        add_unique(state.caveats, "Model review unavailable; rule checks only")
        log(state, "evaluator", "fallback", str(e))

    code_issues = rule_checks(state)
    if code_issues:
        review.issues = code_issues + review.issues
        review.feedback = (" ".join(code_issues) + " " + review.feedback).strip()
        if review.verdict == "pass":
            review.verdict = "revise"
    state.reviews.append(review)
    log(state, "evaluator", "review", review.model_dump())
    return review


# ---------- 4. Reporter ----------
def _cap(conf, ceiling):
    return conf if RANK[conf] <= RANK[ceiling] else ceiling


def run_reporter(state, outcome: str) -> FinalOutput:
    """outcome: 'passed' | 'unresolved' (revision cap hit) | 'escalated'"""
    payload = {"outcome": outcome, "drafts": [d.model_dump() for d in state.drafts],
               "data_gaps": state.data_gaps, "caveats": state.caveats,
               "last_review": state.reviews[-1].model_dump() if state.reviews else None}
    try:
        rep, _ = call_json("reporter", prompts.REPORTER, [user_msg(payload)], ReporterOut.model_validate)
    except LLMError as e:
        rep = ReporterOut(summary="Drafts are ready for your review.", limitations=["Summary generated without the model"])
        log(state, "reporter", "fallback", str(e))
    return _build_final(state, outcome, rep)


def _build_final(state, outcome, rep: ReporterOut) -> FinalOutput:
    n = len(state.drafts)
    order = [i for i in rep.priority_order if 0 <= i < n]
    order += [i for i in range(n) if i not in order]
    ceiling = "low" if outcome != "passed" else "medium" if (state.caveats or state.data_gaps) else "high"
    recs = []
    for i in order:                                       # code, not the model, owns drafts and evidence
        d = state.drafts[i].model_copy()
        d.confidence = _cap(d.confidence, ceiling)
        recs.append(d)

    limitations = list(rep.limitations) + [c for c in state.caveats if c not in rep.limitations]
    if outcome == "unresolved":
        limitations.append("Review issues were not fully resolved after the revision limit: "
                           + "; ".join(state.reviews[-1].issues))
    status = ("needs_input" if outcome == "escalated" or not recs
              else "approved_with_caveats" if outcome == "unresolved" or state.caveats or state.data_gaps
              else "approved")
    return FinalOutput(run_id=state.run_id, status=status, summary=rep.summary, recommendations=recs,
                       data_gaps=state.data_gaps, questions_for_owner=rep.questions_for_owner,
                       limitations=limitations, revisions_used=state.revision_count)


def _error_final(state, reason: str) -> FinalOutput:
    """Last resort: never crash the backend, always return the agreed shape."""
    log(state, "orchestrator", "error", reason)
    rep = ReporterOut(summary="We could not finish a full analysis this time.", limitations=[reason])
    final = _build_final(state, "escalated", rep)
    final.status = "error"
    return final


# ---------- entry point ----------
def run_agent(business_id: str, request: str, sample_mode: bool | None = None) -> FinalOutput:
    if sample_mode is None:
        sample_mode = os.getenv("SAMPLE_MODE", "false").lower() == "true"
    state = RunState(run_id=uuid.uuid4().hex[:8], business_id=business_id, request=request,
                     sample_mode=sample_mode, started_at=time.time())
    try:
        run_planner(state)
        run_analyst(state)
        outcome, review = "unresolved", None
        while True:
            check_deadline(state)
            review = run_evaluator(state)
            if review.verdict == "pass":
                outcome = "passed"
                break
            if review.verdict == "escalate":
                outcome = "escalated"
                break
            if state.revision_count >= MAX_REVISIONS:
                log(state, "orchestrator", "retry_cap", f"{MAX_REVISIONS} revisions used; reporting as-is")
                break
            state.revision_count += 1
            log(state, "orchestrator", "revise", f"round {state.revision_count}")
            run_analyst(state, feedback=review)
        final = run_reporter(state, outcome)
    except RunTimeout as e:
        final = _error_final(state, f"Timed out: {e}")
    except LLMError as e:
        final = _error_final(state, f"Model problem: {e}")

    state.final = final.model_dump()
    Path("logs").mkdir(exist_ok=True)
    Path(f"logs/run_{state.run_id}.json").write_text(state.model_dump_json(indent=2), encoding="utf-8")
    return final
