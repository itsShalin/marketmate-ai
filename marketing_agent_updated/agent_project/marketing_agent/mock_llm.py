
"""Deterministic mock responses for testing orchestration without API credits."""
import json

SEQ = ["get_business_profile", "get_products", "get_inventory", "get_engagement"]
KIND = {
    "get_business_profile": "profile",
    "get_products": "products",
    "get_inventory": "inventory",
    "get_engagement": "engagement",
}


def _rows(result):
    """Extract rows from a tool result while tolerating common API shapes."""
    if isinstance(result, dict):
        data = result.get("data", result)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("items", "products", "inventory", "engagement", "results"):
                if isinstance(data.get(key), list):
                    return data[key]
            return [data]
    return result if isinstance(result, list) else []


def _build_drafts(first):
    results = first.get("tool_results_so_far", {})

    profile_result = results.get("profile", {})
    profile_data = (
        profile_result.get("data", profile_result)
        if isinstance(profile_result, dict)
        else {}
    )
    business_name = profile_data.get("name", "your business")

    products = _rows(results.get("products", {}))
    inventory = _rows(results.get("inventory", {}))
    engagement = _rows(results.get("engagement", {}))

    inventory_by_id = {
        str(row.get("product_id")): row
        for row in inventory
        if isinstance(row, dict) and row.get("product_id") is not None
    }
    product_by_id = {
        str(row.get("id")): row
        for row in products
        if isinstance(row, dict) and row.get("id") is not None
    }

    eligible = []
    for product in products:
        if not isinstance(product, dict) or not product.get("name"):
            continue

        status = str(product.get("status", "")).lower()
        if status in {"discontinued", "inactive", "archived"}:
            continue

        stock_row = inventory_by_id.get(str(product.get("id")))
        if stock_row is None:
            continue

        try:
            stock = int(stock_row.get("stock"))
        except (TypeError, ValueError):
            continue

        if stock <= 0:
            continue

        eligible.append((product, stock_row, stock))

    # Prefer products with available stock and engagement evidence.
    engagement_by_product = {}
    for row in engagement:
        if not isinstance(row, dict):
            continue
        product_id = str(row.get("product_id", ""))
        if product_id in product_by_id:
            engagement_by_product.setdefault(product_id, []).append(row)

    eligible.sort(
        key=lambda item: (
            bool(engagement_by_product.get(str(item[0].get("id")))),
            item[2],
        ),
        reverse=True,
    )

    drafts = []
    for product, stock_row, stock in eligible[:2]:
        name = product["name"]
        product_id = str(product.get("id", ""))
        posts = engagement_by_product.get(product_id, [])
        best_post = max(
            posts,
            key=lambda row: row.get("reach") or 0,
            default=None,
        )

        evidence = [{
            "source": "inventory",
            "detail": f"{name}: {stock} units currently in stock",
        }]
        rationale = f"{name} is available for promotion."
        if best_post:
            evidence.append({
                "source": "engagement",
                "detail": (
                    f"Past {best_post.get('type', 'social')} post reached "
                    f"{best_post.get('reach')} people"
                    if best_post.get("reach") is not None
                    else f"Past post for {name} has engagement data"
                ),
            })
            if best_post.get("posted_at"):
                rationale += f" A previous post was published at {best_post['posted_at']}."

        drafts.append({
            "type": "promo_post",
            "draft": f"Discover {name} from {business_name} — made for your everyday moments.",
            "suggested_time": "18:00",
            "rationale": rationale,
            "evidence": evidence,
            "confidence": "medium" if best_post else "low",
            "warnings": (
                ["Low stock; confirm availability before promoting."]
                if stock <= 3 else []
            ),
        })

    return drafts


def respond(role: str, messages: list) -> str:
    first = json.loads(messages[1]["content"])

    if role == "planner":
        return json.dumps({
            "task_type": "promo_post",
            "num_recommendations": 2,
            "data_needed": ["profile", "products", "inventory", "engagement"],
            "success_criteria": ["every draft cites data", "no out-of-stock promotion"],
            "assumptions": ["deterministic local mock"],
        })

    if role == "analyst":
        have = set(first.get("tool_results_so_far", {}))
        todo = [tool for tool in SEQ if KIND[tool] not in have]
        done = sum(
            1 for message in messages
            if message["role"] == "user" and '"tool_result":' in message["content"]
        )
        if done < len(todo):
            return json.dumps({"action": "call_tool", "tool": todo[done]})

        drafts = _build_drafts(first)
        return json.dumps({
            "action": "final",
            "drafts": drafts,
            "data_gaps": [] if drafts else [
                "No products with confirmed positive inventory were available to recommend."
            ],
        })

    if role == "evaluator":
        return json.dumps({"verdict": "pass", "issues": [], "feedback": ""})

    if role == "reporter":
        count = len(first.get("drafts", []))
        return json.dumps({
            "summary": f"Mock summary: {count} data-backed recommendation(s) prepared for review.",
            "priority_order": list(range(count)),
            "questions_for_owner": [],
            "limitations": [],
        })

    raise ValueError(f"unknown role {role}")
