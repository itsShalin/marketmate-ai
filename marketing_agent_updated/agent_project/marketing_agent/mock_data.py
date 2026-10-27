"""Small synthetic dataset. No real personal data. Scenarios let you test messy-data handling."""
import copy
from pathlib import Path

BASE = {
    "profile": {
        "id": "biz_001", "name": "Sunrise Handmade", "category": "handmade home decor",
        "brand_voice": "warm, playful, proudly local; short sentences; light emoji use",
        "audience": "young families and gift shoppers",
    },
    "products": [
        {"id": "p1", "name": "Jute Tote Bag", "price": 450, "category": "bags", "status": "active"},
        {"id": "p2", "name": "Terracotta Planter", "price": 320, "category": "decor", "status": "active"},
        {"id": "p3", "name": "Handwoven Cotton Throw", "price": 1200, "category": "textiles", "status": "active"},
        {"id": "p4", "name": "Scented Soy Candle", "price": 380, "category": "candles", "status": "active"},
        {"id": "p5", "name": "Bamboo Coaster Set", "price": 250, "category": "kitchen", "status": "active"},
    ],
    "inventory": [
        {"product_id": "p1", "stock": 24, "last_restocked": "2026-10-18"},
        {"product_id": "p2", "stock": 2,  "last_restocked": "2026-09-02"},
        {"product_id": "p3", "stock": 0,  "last_restocked": "2026-08-15"},
        {"product_id": "p4", "stock": 40, "last_restocked": "2026-10-20"},
        {"product_id": "p5", "stock": 15, "last_restocked": "2026-09-28"},
    ],
    "engagement": [
        {"post_id": "e1", "product_id": "p4", "type": "reel",     "posted_at": "2026-10-12T18:30", "likes": 210, "comments": 31, "reach": 3400},
        {"post_id": "e2", "product_id": "p1", "type": "image",    "posted_at": "2026-10-09T11:00", "likes": 95,  "comments": 8,  "reach": 1500},
        {"post_id": "e3", "product_id": "p2", "type": "carousel", "posted_at": "2026-10-05T19:00", "likes": 140, "comments": 14, "reach": 2100},
        {"post_id": "e4", "product_id": "p5", "type": "image",    "posted_at": "2026-10-02T10:30", "likes": 60,  "comments": 3,  "reach": 1100},
        {"post_id": "e5", "product_id": "p4", "type": "reel",     "posted_at": "2026-09-28T18:00", "likes": 188, "comments": 25, "reach": 3000},
        {"post_id": "e6", "product_id": "p3", "type": "carousel", "posted_at": "2026-09-20T19:30", "likes": 120, "comments": 11, "reach": 1900},
    ],
}



def _get_demo():
    """Load and normalize the fictional demo fixture."""
    import json

    fixture = Path(__file__).resolve().parents[1] / "demo_data" / "marketmate_demo.json"
    with fixture.open(encoding="utf-8") as file:
        raw = json.load(file)

    profile = raw["business_profiles"][0]
    inventory = raw["inventory"]
    stock_by_id = {item["product_id"]: item for item in inventory}
    products = []

    for p in raw["products"]:
        stock = stock_by_id.get(p["id"], {})
        products.append({
            "id": p["id"],
            "name": p["name"],
            "price": p["price"],
            "category": p.get("category", "candles"),
            "status": "low_stock" if stock.get("stock_status") == "low_stock" else p.get("status", "active"),
        })

    return {
        "profile": {
            "id": profile["business_id"],
            "name": profile["name"],
            "category": profile["business_type"],
            "brand_voice": ", ".join(profile["brand_voice"]),
            "audience": profile["target_audience"],
        },
        "products": products,
        "inventory": inventory,
        "engagement": [
            {
                "product_id": item["product_id"],
                "type": "post",
                "posted_at": item["post_date"],
                "platform": item["platform"],
                "likes": item["likes"],
                "comments": item["comments"],
                "reach": None,
                "clicks": item.get("clicks", 0),
            }
            for item in raw["engagement"]
        ],
    }


def get_mock(scenario: str = "normal") -> dict:
    import os
    if os.getenv("DEMO_DATA_MODE", "false").lower() == "true":
        return _get_demo()
    d = copy.deepcopy(BASE)
    if scenario == "conflict":
        d["products"][3]["status"] = "discontinued"
    elif scenario == "sparse":
        d["engagement"] = d["engagement"][:2]
        d["engagement"][1]["reach"] = None
        d["profile"]["brand_voice"] = None
    return d

