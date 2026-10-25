import unittest
from types import SimpleNamespace

from marketing_agent.orchestrator import rule_checks
from marketing_agent.state import Evidence, Recommendation


class RuleChecksTests(unittest.TestCase):
    def make_state(self, draft_text, stock=12, status="in_stock"):
        draft = Recommendation(
            type="promo_post",
            draft=draft_text,
            rationale="Test recommendation",
            evidence=[
                Evidence(source="products", detail="Product catalogue")
            ],
        )
        return SimpleNamespace(
            drafts=[draft],
            tool_data={
                "products": [
                    {
                        "id": "c1",
                        "name": "Lavender Calm Candle",
                        "status": status,
                    }
                ],
                "inventory": [{"product_id": "c1", "stock": stock}],
                "engagement": [],
                "profile": {},
            },
        )

    def test_unknown_product_is_flagged(self):
        state = self.make_state("Promote our Jute Tote Bag today!")
        issues = rule_checks(state)

        self.assertTrue(
            any("unsupported product" in issue.lower() for issue in issues),
            f"Expected an unsupported-product issue, got: {issues}",
        )

    def test_second_unknown_mock_product_is_flagged(self):
        state = self.make_state(
            "Wrap up warm with our Handwoven Cotton Throw!"
        )
        issues = rule_checks(state)

        self.assertTrue(
            any("unsupported product" in issue.lower() for issue in issues),
            f"Expected an unsupported-product issue, got: {issues}",
        )

    def test_known_product_is_not_flagged_as_unknown(self):
        state = self.make_state(
            "Discover our Lavender Calm Candle today!"
        )
        issues = rule_checks(state)

        self.assertFalse(
            any("unsupported product" in issue.lower() for issue in issues),
            f"Known product was incorrectly flagged: {issues}",
        )

    def test_out_of_stock_product_is_flagged(self):
        state = self.make_state(
            "Promote Lavender Calm Candle today!",
            stock=0,
        )
        issues = rule_checks(state)

        self.assertTrue(
            any("out of stock" in issue.lower() for issue in issues),
            f"Expected an out-of-stock issue, got: {issues}",
        )

    def test_discontinued_product_is_flagged(self):
        state = self.make_state(
            "Promote Lavender Calm Candle today!",
            stock=12,
            status="discontinued",
        )
        issues = rule_checks(state)

        self.assertTrue(
            any("discontinued" in issue.lower() for issue in issues),
            f"Expected a discontinued-product issue, got: {issues}",
        )

    def test_catalogue_low_stock_status_is_flagged(self):
        state = self.make_state(
            "Promote Lavender Calm Candle today!",
            stock=4,
            status="low_stock",
        )
        issues = rule_checks(state)

        self.assertTrue(
            any(
                "low-stock" in issue.lower()
                or "low stock" in issue.lower()
                for issue in issues
            ),
            f"Expected a low-stock issue, got: {issues}",
        )

    def test_saved_no_discount_preference_flags_discount_offer(self):
        state = self.make_state(
            "Get 20% off our Lavender Calm Candle today!"
        )
        state.memory_context = "Avoid discounts."

        issues = rule_checks(state)

        self.assertTrue(
            any(
                "saved no-discount preference" in issue.lower()
                for issue in issues
            ),
            f"Expected a saved-preference issue, got: {issues}",
        )

    def test_discount_offer_without_saved_preference_is_not_flagged_by_policy(self):
        state = self.make_state(
            "Get 20% off our Lavender Calm Candle today!"
        )
        state.memory_context = ""

        issues = rule_checks(state)

        self.assertFalse(
            any(
                "saved no-discount preference" in issue.lower()
                for issue in issues
            ),
            f"Unexpected saved-preference issue: {issues}",
        )


if __name__ == "__main__":
    unittest.main()
