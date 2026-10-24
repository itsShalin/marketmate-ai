"""Canned replies so you can test the whole orchestration with no API key and no credits (MOCK_LLM=true).
Deliberately makes the Analyst's FIRST draft promote an out-of-stock item, so the revision loop gets exercised."""
import json

SEQ = ["get_business_profile", "get_products", "get_inventory", "get_engagement"]
KIND = {"get_business_profile": "profile", "get_products": "products",
        "get_inventory": "inventory", "get_engagement": "engagement"}


def _draft_ok():
    return {"type": "stock_update", "draft": "Fresh stock alert! Our Jute Tote Bag is back and ready to travel with you.",
            "suggested_time": "Thursday 18:00", "rationale": "Restocked 3 days ago; evening posts reached more people.",
            "evidence": [{"source": "inventory", "detail": "Jute Tote Bag restocked 2026-10-18, 24 units"},
                         {"source": "engagement", "detail": "Reels posted around 18:00 reached 3,000+ people"}],
            "confidence": "high", "warnings": []}


def _draft_bad():
    return {"type": "promo_post", "draft": "Wrap up warm with our Handwoven Cotton Throw!",
            "suggested_time": "Saturday 19:00", "rationale": "Carousels did well in the evening.",
            "evidence": [{"source": "engagement", "detail": "Throw carousel got 120 likes on 2026-09-20"}],
            "confidence": "medium", "warnings": []}


def respond(role: str, messages: list) -> str:
    first = json.loads(messages[1]["content"])
    if role == "planner":
        return json.dumps({"task_type": "promo_post", "num_recommendations": 2,
                           "data_needed": ["profile", "products", "inventory", "engagement"],
                           "success_criteria": ["every draft cites data", "no out-of-stock promotion"],
                           "assumptions": ["mock planner"]})
    if role == "analyst":
        have = set(first.get("tool_results_so_far", {}))
        todo = [t for t in SEQ if KIND[t] not in have]
        done = sum(1 for m in messages if m["role"] == "user" and "\"tool_result\":" in m["content"])
        if done < len(todo):
            return json.dumps({"action": "call_tool", "tool": todo[done]})
        revising = bool(first.get("reviewer_feedback"))
        drafts = [_draft_ok()] if revising else [_draft_ok(), _draft_bad()]
        return json.dumps({"action": "final", "drafts": drafts, "data_gaps": []})
    if role == "evaluator":
        return json.dumps({"verdict": "pass", "issues": [], "feedback": ""})
    if role == "reporter":
        n = len(first.get("drafts", []))
        return json.dumps({"summary": "Mock summary: drafts are ready for your review.",
                           "priority_order": list(range(n)), "questions_for_owner": [], "limitations": []})
    raise ValueError(f"unknown role {role}")
