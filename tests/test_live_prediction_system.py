from datetime import datetime, timedelta, timezone
import unittest

from app.live_prediction_system import LivePredictionSystem, MatchState, ModelType


class LivePredictionSystemTests(unittest.TestCase):
    def setUp(self) -> None:
        self.system = LivePredictionSystem()
        self.system.signup("u1")

    def test_signup_defaults(self) -> None:
        profile = self.system.users["u1"]
        self.assertEqual(profile.coins, 100)
        self.assertEqual(profile.level, "Beginner")

    def test_create_edit_lock_and_settle_correct_prediction(self) -> None:
        self.system.update_match_state(
            MatchState("m1", 1, 2, 10, 0, 5.0, "powerplay")
        )
        event = self.system.create_prediction_event(
            event_id="e1",
            match_id="m1",
            model_type=ModelType.NEXT_OVER_RUNS,
            option_a="Over 9.5",
            option_b="Under 9.5",
            prob_a=0.55,
            prob_b=0.45,
            lock_in_seconds=60,
        )
        pred = self.system.make_prediction("p1", "u1", event.event_id, "Under 9.5")
        self.system.edit_prediction(pred.prediction_id, "Over 9.5")

        lock_time = datetime.now(timezone.utc) + timedelta(seconds=61)
        locked = self.system.lock_started_events(now=lock_time)
        self.assertIn("e1", locked)

        self.system.settle_event("e1", "Over 9.5")
        dashboard = self.system.dashboard("u1")

        self.assertEqual(dashboard["total_points"], 55)
        self.assertEqual(dashboard["coins"], 110)
        self.assertEqual(dashboard["accuracy_percent"], 100.0)

    def test_wrong_prediction_grants_xp_no_penalty(self) -> None:
        event = self.system.create_prediction_event(
            event_id="e2",
            match_id="m1",
            model_type=ModelType.MATCH_WINNER,
            option_a="Team A",
            option_b="Team B",
            prob_a=0.40,
            prob_b=0.60,
            lock_in_seconds=0,
        )
        # Event can be settled directly by backend trigger; user prediction must be before lock.
        event.lock_at = datetime.now(timezone.utc) + timedelta(seconds=10)
        self.system.make_prediction("p2", "u1", "e2", "Team A")

        self.system.lock_started_events(now=datetime.now(timezone.utc) + timedelta(seconds=11))
        self.system.settle_event("e2", "Team B")

        dashboard = self.system.dashboard("u1")
        self.assertEqual(dashboard["total_points"], 0)
        self.assertEqual(dashboard["coins"], 100)
        self.assertEqual(dashboard["xp"], 15)
        self.assertEqual(dashboard["accuracy_percent"], 0.0)


if __name__ == "__main__":
    unittest.main()
