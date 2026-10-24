"""Canned replies so you can test the whole orchestration with no API key and no credits (MOCK_LLM=true).
Deliberately makes the Analyst's FIRST draft promote an out-of-stock item, so the revision loop gets exercised."""
import json

SEQ = ["get_business_profile", "get_products", "get_inventory", "get_engagement"]
KIND = {"get_business_profile": "profile", "get_products": "products",
        "get_inventory": "inventory", "get_engagement": "engagement"}




def _draft_ok(tool_data):
    products = tool_data.get("products", [])
    inventory = tool_data.get("inventory", [])
    engagement = tool_data.get("engagement", [])
    profile = tool_data.get("profile", {})

    inventory_by_product = {
        item.get("product_id"): item
        for item in inventory
    }

    # Choose an active product that has stock available.
    product = next(
        (
            item for item in products
            if item.get("status") in {"active", "in_stock"}
            and inventory_by_product.get(item.get("id"), {}).get("stock", 0) > 3
        ),
        None,
    )

    if product is None:
        return {
            "type": "promo_post",
            "draft": "We’re preparing something special for you. Stay tuned!",
            "suggested_time": None,
            "rationale": "No active product with sufficient confirmed stock was found.",
            "evidence": [],
            "confidence": "low",
            "warnings": ["No eligible in-stock product was available to promote."],
        }

    stock = inventory_by_product[product["id"]]["stock"]
    product_posts = [
        post for post in engagement
        if post.get("product_id") == product["id"]
    ]
    best_post = max(product_posts, key=lambda post: post.get("reach", 0), default=None)

    evidence = [
        {
            "source": "products",
            "detail": (
                f"{product['name']} is listed as {product.get('status', 'unknown')} "
                f"at price {product.get('price', 'unknown')}."
            ),
        },
        {
            "source": "inventory",
            "detail": f"{product['name']} has {stock} units in stock.",
        },
    ]

    suggested_time = None
    warnings = []

    if best_post:
        evidence.append({
            "source": "engagement",
            "detail": (
                f"A previous {best_post.get('type', 'unknown')} post for "
                f"{product['name']} reached {best_post.get('reach', 0)} people, "
                f"with {best_post.get('likes', 0)} likes and "
                f"{best_post.get('comments', 0)} comments."
            ),
        })
        posted_at = best_post.get("posted_at", "")
        if "T" in posted_at:
            suggested_time = posted_at.split("T", 1)[1][:5]
    else:
        warnings.append("No previous engagement record was found for this product.")

    if stock <= 3:
        warnings.append("Low stock: avoid aggressive promotion.")

    business_name = profile.get("name", "our shop")

    return {
        "type": "promo_post",
        "draft": (
            f"Bring a little handmade charm into your day! "
            f"Meet our {product['name']} from {business_name}. "
            f"Message us to learn more."
        ),
        "suggested_time": suggested_time,
        "rationale": (
            f"{product['name']} is available and has {stock} units in stock."
            + (
                " Its previous post provides a useful engagement reference."
                if best_post else
                " There is no previous engagement record for this product."
            )
        ),
        "evidence": evidence,
        "confidence": "medium" if best_post else "low",
        "warnings": warnings,
    }



def _draft_bad():
    return {"type": "promo_post", "draft": "Wrap up warm with our Handwoven Cotton Throw!",
            "suggested_time": "Saturday 19:00", "rationale": "Carousels did well in the evening.",
            "evidence": [{"source": "engagement", "detail": "Throw carousel got 120 likes on 2026-09-20"}],
            "confidence": "medium", "warnings": []}



def respond(role: str, messages: list) -> str:
    first = json.loads(messages[1]["content"])

    if role == "planner":
        return json.dumps({
            "task_type": "promo_post",
            "num_recommendations": 2,
            "data_needed": ["profile", "products", "inventory", "engagement"],
            "success_criteria": ["every draft cites data", "no out-of-stock promotion"],
            "assumptions": ["mock planner"]
        })

    
    if role == "analyst":
        have = set(first.get("tool_results_so_far", {}))
        todo = [t for t in SEQ if KIND[t] not in have]
        done = sum(
            1 for m in messages
            if m["role"] == "user" and '"tool_result":' in m["content"]
        )

        if done < len(todo):
            return json.dumps({"action": "call_tool", "tool": todo[done]})

        tool_data = first.get("tool_results_so_far", {})
        revising = bool(first.get("reviewer_feedback"))

        
        if revising:
            first_draft = _draft_ok(tool_data)

            # Offer two different creative angles for the eligible product.
            second_draft = dict(first_draft)
            original_draft = first_draft["draft"]
            second_draft["draft"] = original_draft.replace(
                "Bring a little handmade charm into your day!",
                "Make your home feel a little cozier today!"
            )
            second_draft["rationale"] = (
                first_draft["rationale"]
                + " This alternative uses a different promotional angle."
            )

            drafts = [first_draft, second_draft]
        else:
            # Intentionally flawed first draft to exercise evaluator revision.
            drafts = [_draft_ok(tool_data), _draft_bad()]
        return json.dumps({
            "action": "final",
            "drafts": drafts,
            "data_gaps": []
        })


    if role == "evaluator":
        revision_round = first.get("revision_round", 0)

        if revision_round == 0:
            return json.dumps({
                "verdict": "revise",
                "issues": ["Mock test: verify the revision loop."],
                "feedback": "Please revise the drafts for this test."
            })

        return json.dumps({
            "verdict": "pass",
            "issues": [],
            "feedback": ""
        })

    if role == "reporter":
        n = len(first.get("drafts", []))
        return json.dumps({
            "summary": "Mock summary: drafts are ready for your review.",
            "priority_order": list(range(n)),
            "questions_for_owner": [],
            "limitations": []
        })

    raise ValueError(f"unknown role {role}")
