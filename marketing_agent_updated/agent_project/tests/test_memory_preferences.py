import unittest

from marketing_agent.mock_llm import _build_drafts


class MemoryPreferenceTests(unittest.TestCase):
    def test_saved_no_discount_preference_is_respected(self):
        payload = {
            "remembered_preferences": (
                "[MEMORY CONTEXT]\n"
                "- Avoid discounts. Use a premium, friendly tone "
                "for marketing posts.\n"
                "[/MEMORY CONTEXT]"
            ),
            "tool_results_so_far": {
                "profile": {"data": {"name": "Cozy Candles"}},
                "products": [
                    {"id": "p1", "name": "Lavender Calm Candle",
                     "status": "in_stock"}
                ],
                "inventory": [{"product_id": "p1", "stock": 12}],
                "engagement": []
            }
        }

        drafts = _build_drafts(payload)

        self.assertTrue(drafts, "Expected at least one draft")
        for draft in drafts:
            text = (draft["draft"] + " " + draft["rationale"]).lower()
            self.assertNotIn("discount", text)
            self.assertNotIn("50% off", text)
            self.assertNotIn("buy one get one", text)


if __name__ == "__main__":
    unittest.main()
