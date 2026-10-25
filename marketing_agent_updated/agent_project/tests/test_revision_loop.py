
import unittest
from unittest.mock import patch

from marketing_agent import orchestrator
from marketing_agent.state import (
    Evidence,
    Recommendation,
    Review,
    ReporterOut,
)


class RevisionLoopTests(unittest.TestCase):
    def test_bad_draft_is_revised_before_approval(self):
        bad_draft = Recommendation(
            type="promo_post",
            draft="Promote Lavender Calm Candle today!",
            rationale="Initial test draft",
            evidence=[
                Evidence(
                    source="inventory",
                    detail="Lavender Calm Candle: 0 units in stock",
                )
            ],
        )

        corrected_draft = Recommendation(
            type="promo_post",
            draft="Discover Vanilla Comfort Candle today!",
            rationale="Revised to use an available product",
            evidence=[
                Evidence(
                    source="inventory",
                    detail="Vanilla Comfort Candle: 4 units in stock",
                )
            ],
        )

        feedback_received = []

        def fake_analyst(state, feedback=None):
            if feedback is None:
                state.drafts = [bad_draft.model_copy(deep=True)]
            else:
                feedback_received.append(feedback)
                state.drafts = [corrected_draft.model_copy(deep=True)]

        reviews = [
            Review(
                verdict="revise",
                issues=["Initial draft promotes an out-of-stock product"],
                feedback="Choose a product with positive stock.",
            ),
            Review(
                verdict="pass",
                feedback="The revised draft passes.",
            ),
        ]

        def fake_evaluator(state):
            review = reviews.pop(0)
            state.reviews.append(review)
            return review

        with (
            patch.object(orchestrator, "run_planner"),
            patch.object(
                orchestrator,
                "run_analyst",
                side_effect=fake_analyst,
            ),
            patch.object(
                orchestrator,
                "run_evaluator",
                side_effect=fake_evaluator,
            ),
            patch.object(
                orchestrator,
                "run_reporter",
                side_effect=lambda state, outcome: orchestrator._build_final(
                    state,
                    outcome,
                    ReporterOut(summary="Ready for owner review."),
                ),
            ),
            patch.object(orchestrator.memory, "enabled", return_value=False),
            patch.object(orchestrator.Path, "mkdir"),
            patch.object(orchestrator.Path, "write_text"),
        ):
            result = orchestrator.run_agent(
                "test-business",
                "Create a promotional post",
                sample_mode=True,
            )

        self.assertEqual(result.status, "approved")
        self.assertEqual(result.revisions_used, 1)
        self.assertEqual(len(feedback_received), 1)
        self.assertEqual(feedback_received[0].verdict, "revise")
        self.assertEqual(len(result.recommendations), 1)
        self.assertEqual(
            result.recommendations[0].draft,
            corrected_draft.draft,
        )

    def test_discount_preference_triggers_revision_before_approval(self):
        bad_draft = Recommendation(
            type="promo_post",
            draft="Get 20% off our Lavender Calm Candle today!",
            rationale="Initial test draft",
            evidence=[
                Evidence(
                    source="products",
                    detail="Known catalogue product",
                )
            ],
        )

        corrected_draft = Recommendation(
            type="promo_post",
            draft="Discover our Lavender Calm Candle today!",
            rationale="Revised to respect the saved no-discount preference",
            evidence=[
                Evidence(
                    source="products",
                    detail="Known catalogue product",
                )
            ],
        )

        feedback_received = []

        def fake_analyst(state, feedback=None):
            # Supply consistent backend data on both review rounds.
            state.tool_data = {
                "profile": {"name": "Cozy Candles"},
                "products": [
                    {
                        "id": "c1",
                        "name": "Lavender Calm Candle",
                        "status": "in_stock",
                    }
                ],
                "inventory": [
                    {"product_id": "c1", "stock": 12}
                ],
                "engagement": [],
            }

            if feedback is None:
                state.drafts = [bad_draft.model_copy(deep=True)]
            else:
                feedback_received.append(feedback)
                state.drafts = [corrected_draft.model_copy(deep=True)]

        def fake_planner(state):
            # Simulate a preference recalled from H-MEM.
            state.memory_context = "Avoid discounts."

        def fake_evaluator(state):
            review = Review(
                verdict="pass",
                feedback="Mock evaluator review.",
            )

            # Use the real deterministic rules.
            issues = orchestrator.rule_checks(state)

            if issues:
                review.issues = issues + review.issues
                review.feedback = " ".join(issues)
                review.verdict = "revise"

            state.reviews.append(review)
            return review

        def fake_reporter(state, outcome):
            return orchestrator._build_final(
                state,
                outcome,
                ReporterOut(summary="Ready for owner review."),
            )

        with (
            patch.object(
                orchestrator,
                "run_planner",
                side_effect=fake_planner,
            ),
            patch.object(
                orchestrator,
                "run_analyst",
                side_effect=fake_analyst,
            ),
            patch.object(
                orchestrator,
                "run_evaluator",
                side_effect=fake_evaluator,
            ),
            patch.object(
                orchestrator,
                "run_reporter",
                side_effect=fake_reporter,
            ),
            patch.object(orchestrator.memory, "enabled", return_value=False),
            patch.object(orchestrator.Path, "mkdir"),
            patch.object(orchestrator.Path, "write_text"),
        ):
            result = orchestrator.run_agent(
                "test-business",
                "Create a promotional post",
                sample_mode=True,
            )

        self.assertEqual(result.status, "approved")
        self.assertEqual(result.revisions_used, 1)
        self.assertEqual(len(feedback_received), 1)

        self.assertTrue(
            any(
                "saved no-discount preference" in issue.lower()
                for issue in feedback_received[0].issues
            ),
            f"Expected preference feedback, got: {feedback_received[0].issues}",
        )

        self.assertNotIn(
            "20% off",
            result.recommendations[0].draft.lower(),
        )


if __name__ == "__main__":
    unittest.main()
