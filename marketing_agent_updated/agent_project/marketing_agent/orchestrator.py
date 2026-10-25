"""Runs Planner -> Analyst -> Evaluator (-> revise loop) -> Reporter over a shared RunState.
Every loop is bounded: model retries, JSON repairs, tool retries, tool steps, revision rounds, total run time."""
import json
import os
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from . import prompts, memory, budget
from .llm import LLMError, call_json
from .state import (FinalOutput, Message, Plan, ReporterOut, Recommendation, Review, RunState)
from .tools import ENDPOINTS, call_tool
from .mock_data import get_mock

MAX_REVISIONS = int(os.getenv("MAX_REVISIONS", "2"))
MAX_TOOL_STEPS = int(os.getenv("MAX_TOOL_STEPS", "6"))
RUN_TIMEOUT_S = float(os.getenv("RUN_TIMEOUT_S", "240"))
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
    budget.remaining()
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

def _rcpt(state):
    return lambda role, r: log(state, role, "receipt", r)

# ---------- 1. Planner ----------
def run_planner(state):
    try:
        plan, _ = call_json("planner", prompts.PLANNER,
                            [user_msg({"request": state.request, "business_id": state.business_id, "remembered_preferences": state.memory_context})],
                            Plan.model_validate, on_receipt=_rcpt(state))
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
        return {"action": "final", "drafts": drafts, "data_gaps": gaps, "selection_notes": [str(x) for x in d.get("selection_notes", [])]}
    raise ValueError("action must be 'call_tool' or 'final'")


def fetch_planned_data(state):
    """Execute the Planner's data selection without a model round trip per GET."""
    by_kind = {kind: name for name, (kind, _) in ENDPOINTS.items()}
    for kind in state.plan.data_needed:
        if kind in state.tool_data:
            continue
        check_deadline(state)
        name = by_kind[kind]
        log(state, "orchestrator", "planned_tool_call", name)
        result = call_tool(name, state.business_id, state.sample_mode)
        state.tool_data[kind] = result["data"]
        if result["source"] == "sample_fallback":
            add_unique(state.data_gaps, f"Backend unreachable for {kind}; sample data used")
            add_unique(state.caveats, "Backend fallback used")
        log(state, "orchestrator", "tool_result", {"tool": name, "source": result["source"]})


def run_analyst(state, feedback: Review | None = None):
    fetch_planned_data(state)
    first = {"request": state.request, "plan": state.plan.model_dump(),
             "tool_results_so_far": state.tool_data,
             "remembered_preferences": state.memory_context,
             "previous_drafts": [d.model_dump() for d in state.drafts],
             "reviewer_feedback": feedback.model_dump() if feedback else None}
    messages = [user_msg(first)]

    for _ in range(MAX_TOOL_STEPS):
        check_deadline(state)
        step, raw = call_json("analyst", prompts.ANALYST, messages, _validate_step, on_receipt=_rcpt(state))
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
    step, _ = call_json("analyst", prompts.ANALYST, messages, _validate_step, on_receipt=_rcpt(state))
    if step["action"] != "final":
        raise LLMError("analyst did not finish within the tool budget")
    _accept_final(state, step)


def _accept_final(state, step):
    state.drafts = step["drafts"]
    state.selection_notes = step.get("selection_notes", [])
    # Revisions may resolve gaps; retain only explicit backend-fallback provenance.
    state.data_gaps = [g for g in state.data_gaps if g.startswith("Backend unreachable for ")]
    for g in step["data_gaps"]:
        add_unique(state.data_gaps, g)
    log(state, "analyst", "draft", f"{len(state.drafts)} drafts, {len(step['data_gaps'])} data gaps")


# ---------- 3. Evaluator (LLM critic + deterministic rule checks against the raw data) ----------

def rule_checks(state):
    """Check drafts against backend data and saved preferences."""
    issues = []
    inv = {
        r.get("product_id"): r
        for r in rows(state.tool_data.get("inventory", []))
    }
    products = rows(state.tool_data.get("products", []))

    memory_text = (
        getattr(state, "memory_context", "") or ""
    ).casefold()

    no_discount_policy = bool(
        re.search(
            r"\b(avoid discounts|no discounts|never offer discounts|"
            r"do not offer discounts|don't offer discounts)\b",
            memory_text,
        )
    )

    catalogue_names = {
        str(p.get("name", "")).strip().casefold()
        for p in products
        if str(p.get("name", "")).strip()
    }
    sample_products = rows(
        get_mock(os.getenv("MOCK_SCENARIO", "normal")).get("products", [])
    )
    profile_text = json.dumps(
        state.tool_data.get("profile", {})
    ).lower()
    engagement = rows(state.tool_data.get("engagement", []))

    for i, d in enumerate(state.drafts):
        if not d.evidence:
            issues.append(f"Draft {i}: no evidence cited")

        for evidence in d.evidence:
            if not state.tool_data.get(evidence.source):
                issues.append(
                    f"Draft {i}: evidence cites unavailable source "
                    f"{evidence.source}"
                )

        text = d.draft.lower()

        if no_discount_policy and re.search(
            r"\b(\d{1,3}\s*%\s*off|discounts?\s+of\s+\d+%|"
            r"buy one get one|bogo|use code \w+ for \w*discount)\b",
            text,
        ):
            issues.append(
                f"Draft {i}: violates the saved no-discount preference; "
                "remove the discount offer"
            )

        for candidate in sample_products:
            name = str(candidate.get("name", "")).strip()
            if (
                name
                and name.casefold() not in catalogue_names
                and name.casefold() in text
            ):
                issues.append(
                    f"Draft {i}: mentions unsupported product '{name}' "
                    "not present in this business catalogue"
                )

        if re.search(
            r"\b(visit|come|drop|stop|pick)\b.*"
            r"\b(studio|store|shop|showroom|pickup|pick up)\b",
            text,
        ) and not any(
            word in profile_text
            for word in (
                "address", "studio", "storefront",
                "showroom", "pickup"
            )
        ):
            issues.append(
                f"Draft {i}: physical visit or pickup is unsupported "
                "by the business profile; remove that invitation"
            )

        for p in products:
            name = str(p.get("name", "")).strip()
            if not name or name.lower() not in text:
                continue

            posts = [
                r for r in engagement
                if r.get("product_id") == p.get("id")
            ]

            if d.suggested_time and len(posts) < 2:
                d.confidence = _cap(d.confidence, "medium")
                note = (
                    f"Timing for {name} is tentative: based on "
                    f"{len(posts)} matching historical post(s), "
                    "not a demonstrated pattern."
                )
                add_unique(d.warnings, note)
                if not d.suggested_time.lower().startswith("tentative:"):
                    d.suggested_time = "Tentative: " + d.suggested_time

            stock = inv.get(p.get("id"), {}).get("stock")

            status = str(p.get("status", "")).lower()

            if status in ("discontinued", "inactive"):
                issues.append(
                    f"Draft {i}: promotes '{name}' which is "
                    f"{status}"
                )

            has_low_stock_warning = any(
                "low stock" in warning.lower()
                or "low-stock" in warning.lower()
                for warning in d.warnings
            )

            if status == "low_stock" and not has_low_stock_warning:
                issues.append(
                    f"Draft {i}: '{name}' is marked low stock in the "
                    "product catalogue; add a low-stock warning"
                )

            if stock is None:
                if not d.warnings:
                    issues.append(
                        f"Draft {i}: stock for '{name}' is unknown; "
                        "add a warning"
                    )
            elif stock <= 0:
                issues.append(
                    f"Draft {i}: promotes '{name}' which is out of stock "
                    "(0 units)"
                )
            elif stock <= LOW_STOCK and not has_low_stock_warning:
                issues.append(
                    f"Draft {i}: '{name}' has only {stock} units; "
                    "add a low-stock warning"
                )

    return issues

def run_evaluator(state) -> Review:
    profile = state.tool_data.get("profile") or {}
    payload = {
        "plan": state.plan.model_dump(),
        "brand_voice": profile.get("brand_voice"),
        "drafts": [d.model_dump() for d in state.drafts],
        "data_gaps": state.data_gaps,
        "source_data": state.tool_data,
        "selection_notes": state.selection_notes,
        "revision_round": state.revision_count,
        "remembered_preferences": state.memory_context,
    }

    try:
        review, _ = call_json(
            "evaluator",
            prompts.EVALUATOR,
            [user_msg(payload)],
            Review.model_validate,
            temperature=0.0,
            on_receipt=_rcpt(state),
        )
    except LLMError as e:
        review = Review(
            verdict="pass",
            feedback="Model review unavailable; rule checks only",
        )
        add_unique(
            state.caveats,
            "Model review unavailable; rule checks only",
        )
        log(state, "evaluator", "fallback", str(e))

    code_issues = rule_checks(state)
    if code_issues:
        review.issues = code_issues + review.issues
        review.feedback = (
            " ".join(code_issues) + " " + review.feedback
        ).strip()
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
               "data_gaps": state.data_gaps, "selection_notes": state.selection_notes, "caveats": state.caveats,
               "last_review": state.reviews[-1].model_dump() if state.reviews else None}
    if budget.remaining() < 20:
        log(state, "reporter", "budget_fallback", "Skipping optional model report to return reviewed results")
        return _build_final(state, outcome, ReporterOut(summary="", limitations=[]))
    try:
        rep, _ = call_json("reporter", prompts.REPORTER, [user_msg(payload)], ReporterOut.model_validate, on_receipt=_rcpt(state))
    except LLMError as e:
        rep = ReporterOut(summary="Drafts are ready for your review.", limitations=["Summary generated without the model"])
        log(state, "reporter", "fallback", str(e))
    return _build_final(state, outcome, rep)


def final_summary(recs, outcome):
    if not recs:
        return "No recommendations are ready; check the limitations and requested information."
    confidence = min((d.confidence for d in recs), key=RANK.get)
    suffix = " Review issues remain unresolved." if outcome == "unresolved" else " More information is needed." if outcome == "escalated" else ""
    return f"{len(recs)} recommendation(s) prepared for owner review. Lowest recommendation confidence: {confidence}." + suffix


def _build_final(state, outcome, rep: ReporterOut) -> FinalOutput:
    n = len(state.drafts)
    order = list(dict.fromkeys(i for i in rep.priority_order if 0 <= i < n))
    order += [i for i in range(n) if i not in order]
    ceiling = "low" if outcome != "passed" else "medium" if (state.caveats or state.data_gaps) else "high"
    recs = []
    for i in order:                                       # code, not the model, owns drafts and evidence
        d = state.drafts[i].model_copy()
        d.confidence = _cap(d.confidence, ceiling)
        recs.append(d)

    limitations = list(dict.fromkeys(rep.limitations + state.selection_notes + state.data_gaps)) + [c for c in state.caveats if c not in rep.limitations]
    if outcome == "unresolved":
        limitations.append("Review issues were not fully resolved after the revision limit: "
                           + "; ".join(state.reviews[-1].issues))
    status = ("needs_input" if outcome in ("escalated", "unresolved") or not recs
              else "approved_with_caveats" if outcome == "unresolved" or state.caveats or state.data_gaps
              else "approved")
    return FinalOutput(run_id=state.run_id, status=status, summary=final_summary(recs, outcome), recommendations=recs,
                       data_gaps=state.data_gaps, questions_for_owner=rep.questions_for_owner,
                       limitations=limitations, revisions_used=state.revision_count)


def _error_final(state, reason: str) -> FinalOutput:
    """Last resort: never crash the backend, always return the agreed shape."""
    log(state, "orchestrator", "error", reason)
    rep = ReporterOut(summary="We could not finish a full analysis this time.", limitations=[reason])
    final = _build_final(state, "escalated", rep)
    final.status = "error"
    final.summary = "Analysis could not be completed; check the limitations."
    return final


# ---------- entry point ----------
def _run_agent(business_id: str, request: str, sample_mode: bool | None = None) -> FinalOutput:
    if sample_mode is None:
        sample_mode = os.getenv("SAMPLE_MODE", "false").lower() == "true"
    state = RunState(run_id=uuid.uuid4().hex[:8], business_id=business_id, request=request,
                     sample_mode=sample_mode, started_at=time.time())
    try:
        if memory.enabled():
            try:
                recalled = memory.recall(business_id, request)
                state.memory_context = recalled["context"]
                state.memory_trace = recalled
                log(state, "hmem", "recall", recalled)
            except memory.MemoryError as e:
                add_unique(state.caveats, "Persistent memory unavailable; preferences could not be recalled")
                log(state, "hmem", "unavailable", str(e))
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
    except (RunTimeout, budget.DeadlineExceeded) as e:
        final = _error_final(state, f"Timed out: {e}")
    except LLMError as e:
        final = _error_final(state, f"Model problem: {e}")

    # Only a reusable brand field is captured; never persist inventory or model drafts as facts.
    profile = state.tool_data.get("profile") or {}
    if final.status != "error" and memory.enabled() and not state.sample_mode and "Backend fallback used" not in state.caveats and isinstance(profile, dict) and isinstance(profile.get("brand_voice"), str) and profile["brand_voice"].strip():
        try:
            saved = memory.remember(business_id, "brand_voice", profile["brand_voice"], source="backend_profile")
            log(state, "hmem", "profile_capture", saved)
        except (memory.MemoryError, budget.DeadlineExceeded) as e:
            warning = "Brand preference could not be saved to persistent memory"
            if warning not in final.limitations:
                final.limitations.append(warning)
            if final.status == "approved":
                final.status = "approved_with_caveats"
            log(state, "hmem", "unavailable", str(e))
    state.final = final.model_dump()
    Path("logs").mkdir(exist_ok=True)
    Path(f"logs/run_{state.run_id}.json").write_text(state.model_dump_json(indent=2), encoding="utf-8")
    return final


def run_agent(business_id: str, request: str, sample_mode: bool | None = None) -> FinalOutput:
    token = budget.deadline.set(time.monotonic() + RUN_TIMEOUT_S)
    try:
        return _run_agent(business_id, request, sample_mode)
    finally:
        budget.deadline.reset(token)
