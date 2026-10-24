"""Small synthetic dataset. No real personal data. Scenarios let you test messy-data handling."""
import copy

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


def get_mock(scenario: str = "normal") -> dict:
    d = copy.deepcopy(BASE)
    if scenario == "conflict":
        # Catalogue says discontinued, inventory says 40 units restocked yesterday.
        d["products"][3]["status"] = "discontinued"
    elif scenario == "sparse":
        d["engagement"] = d["engagement"][:2]
        d["engagement"][1]["reach"] = None
        d["profile"]["brand_voice"] = None
    return d
