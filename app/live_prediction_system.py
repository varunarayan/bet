from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Dict, List, Optional


class ModelType(str, Enum):
    NEXT_OVER_RUNS = "next_over_runs"
    TEN_OVER_TOTAL = "ten_over_total"
    MATCH_WINNER = "match_winner"


class EventStatus(str, Enum):
    OPEN = "open"
    LOCKED = "locked"
    SETTLED = "settled"


@dataclass
class UserProfile:
    user_id: str
    coins: int = 100
    level: str = "Beginner"
    xp: int = 0
    points: int = 0
    streak_current: int = 0
    streak_best: int = 0
    correct_predictions: int = 0
    total_predictions: int = 0


@dataclass
class MatchState:
    match_id: str
    over_number: int
    ball_in_over: int
    runs_total: int
    wickets: int
    run_rate: float
    phase: str
    captured_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class PredictionEvent:
    event_id: str
    match_id: str
    model_type: ModelType
    option_a: str
    option_b: str
    prob_a: float
    prob_b: float
    lock_at: datetime
    status: EventStatus = EventStatus.OPEN
    result_option: Optional[str] = None


@dataclass
class UserPrediction:
    prediction_id: str
    user_id: str
    event_id: str
    selected_option: str
    potential_points: int = 50
    status: EventStatus = EventStatus.OPEN
    is_correct: Optional[bool] = None


class LivePredictionSystem:
    """Minimal in-memory implementation of the live cricket prediction loop."""

    def __init__(self) -> None:
        self.users: Dict[str, UserProfile] = {}
        self.match_states: Dict[str, MatchState] = {}
        self.events: Dict[str, PredictionEvent] = {}
        self.user_predictions: Dict[str, UserPrediction] = {}

    def signup(self, user_id: str) -> UserProfile:
        profile = UserProfile(user_id=user_id)
        self.users[user_id] = profile
        return profile

    def update_match_state(self, state: MatchState) -> None:
        self.match_states[state.match_id] = state

    def create_prediction_event(
        self,
        event_id: str,
        match_id: str,
        model_type: ModelType,
        option_a: str,
        option_b: str,
        prob_a: float,
        prob_b: float,
        lock_in_seconds: int,
    ) -> PredictionEvent:
        event = PredictionEvent(
            event_id=event_id,
            match_id=match_id,
            model_type=model_type,
            option_a=option_a,
            option_b=option_b,
            prob_a=prob_a,
            prob_b=prob_b,
            lock_at=datetime.now(timezone.utc) + timedelta(seconds=lock_in_seconds),
        )
        self.events[event_id] = event
        return event

    def make_prediction(self, prediction_id: str, user_id: str, event_id: str, selected_option: str) -> UserPrediction:
        event = self.events[event_id]
        if event.status != EventStatus.OPEN:
            raise ValueError("Prediction event is not open")
        if datetime.now(timezone.utc) >= event.lock_at:
            raise ValueError("Prediction event already started and is locked")

        prediction = UserPrediction(
            prediction_id=prediction_id,
            user_id=user_id,
            event_id=event_id,
            selected_option=selected_option,
        )
        self.user_predictions[prediction_id] = prediction
        return prediction

    def edit_prediction(self, prediction_id: str, new_option: str) -> UserPrediction:
        prediction = self.user_predictions[prediction_id]
        event = self.events[prediction.event_id]
        if event.status != EventStatus.OPEN or datetime.now(timezone.utc) >= event.lock_at:
            raise ValueError("Cannot edit prediction after lock")
        prediction.selected_option = new_option
        return prediction

    def lock_started_events(self, now: Optional[datetime] = None) -> List[str]:
        now = now or datetime.now(timezone.utc)
        locked: List[str] = []
        for event in self.events.values():
            if event.status == EventStatus.OPEN and now >= event.lock_at:
                event.status = EventStatus.LOCKED
                locked.append(event.event_id)

        for prediction in self.user_predictions.values():
            if prediction.event_id in locked:
                prediction.status = EventStatus.LOCKED
        return locked

    def settle_event(self, event_id: str, result_option: str) -> None:
        event = self.events[event_id]
        if event.status not in {EventStatus.LOCKED, EventStatus.OPEN}:
            raise ValueError("Event already settled")

        # Settle event and linked user predictions.
        event.status = EventStatus.SETTLED
        event.result_option = result_option

        for prediction in self.user_predictions.values():
            if prediction.event_id != event_id:
                continue

            profile = self.users[prediction.user_id]
            prediction.status = EventStatus.SETTLED
            prediction.is_correct = prediction.selected_option == result_option
            profile.total_predictions += 1

            if prediction.is_correct:
                profile.correct_predictions += 1
                profile.streak_current += 1
                profile.streak_best = max(profile.streak_best, profile.streak_current)
                streak_bonus = 5 * profile.streak_current
                profile.points += 50 + streak_bonus
                profile.coins += 10
            else:
                profile.streak_current = 0
                profile.xp += 15

            profile.level = self._compute_level(profile.xp, profile.points)

    def dashboard(self, user_id: str) -> dict:
        profile = self.users[user_id]
        accuracy = (
            (profile.correct_predictions / profile.total_predictions) * 100
            if profile.total_predictions
            else 0.0
        )
        history = [
            {
                "prediction_id": p.prediction_id,
                "event_id": p.event_id,
                "selected_option": p.selected_option,
                "is_correct": p.is_correct,
                "status": p.status.value,
            }
            for p in self.user_predictions.values()
            if p.user_id == user_id
        ]
        return {
            "total_points": profile.points,
            "accuracy_percent": round(accuracy, 2),
            "coins": profile.coins,
            "xp": profile.xp,
            "level": profile.level,
            "streak_current": profile.streak_current,
            "streak_best": profile.streak_best,
            "history": history,
        }

    @staticmethod
    def _compute_level(xp: int, points: int) -> str:
        score = xp + points
        if score >= 500:
            return "Expert"
        if score >= 250:
            return "Pro"
        if score >= 100:
            return "Intermediate"
        return "Beginner"
