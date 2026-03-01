# Live Cricket Prediction Startup System

This document converts the provided flow into an implementable product blueprint for an MVP.

## 1) Product Flow (from user journey)

1. User signs up / logs in.
2. Profile is auto-created:
   - `coins = 100`
   - `level = Beginner`
3. System connects to a live cricket data provider (ball-by-ball stream).
4. Match state is continuously updated (runs, wickets, run rate, phase).
5. Three prediction models run in parallel:
   - Model 1: Next over runs (Over/Under probability)
   - Model 2: 10-over total projection (Over/Under probability)
   - Model 3: Match winner (team win probability)
6. User makes live predictions against available events.
7. When event starts:
   - Prediction is locked.
   - If not started, user can edit.
8. Event result is computed.
9. Reward logic:
   - Correct: points + coins + streak bonus.
   - Wrong: XP only (no penalties).
10. Gamification engine updates streak, levels, badges, and daily challenges.
11. Dashboard refreshes with points, accuracy, rank, and prediction history.
12. Loop continues until match ends.

---

## 2) Core Services (MVP)

### 2.1 Auth & Profile Service
- Signup/login via JWT sessions.
- On first login, create profile defaults.
- Exposes:
  - `POST /auth/signup`
  - `POST /auth/login`
  - `GET /me`

### 2.2 Live Match Ingestion Service
- Consumes cricket API/websocket feed.
- Normalizes incoming events to internal schema.
- Publishes events to queue/topic:
  - `ball_update`
  - `over_end`
  - `innings_phase_change`

### 2.3 Feature + Model Service
- Derives live features (last 6 balls, wickets in hand, required RR, etc.).
- Runs 3 models and emits prediction markets with probabilities.
- Stores model snapshots for auditability.

### 2.4 Prediction Market Service
- Creates user-visible prediction events.
- Handles locking logic based on start timestamps/ball triggers.
- Supports update/cancel only before lock.

### 2.5 Scoring & Reward Service
- Compares user picks vs settled outcomes.
- Applies reward policy:
  - `correct => +points +coins +streak`
  - `wrong => +xp`
- Emits user progression events.

### 2.6 Gamification Service
- Tracks streaks and level progression.
- Awards badges and daily challenge completions.
- Computes leaderboard/rank.

### 2.7 Dashboard API
- Returns aggregated user stats:
  - total points
  - accuracy %
  - rank
  - prediction history

---

## 3) Suggested Data Model (relational)

### `users`
- `id` (PK)
- `email`
- `password_hash`
- `created_at`

### `profiles`
- `user_id` (PK/FK users.id)
- `coins` (default 100)
- `xp` (default 0)
- `level` (default "Beginner")
- `streak_current` (default 0)
- `streak_best` (default 0)

### `matches`
- `id` (PK)
- `provider_match_id`
- `team_a`
- `team_b`
- `status` (scheduled/live/ended)
- `start_time`

### `match_states`
- `id` (PK)
- `match_id` (FK)
- `over_number`
- `ball_in_over`
- `runs_total`
- `wickets`
- `run_rate`
- `phase` (powerplay/middle/death)
- `captured_at`

### `prediction_events`
- `id` (PK)
- `match_id` (FK)
- `model_type` (next_over_runs/ten_over_total/match_winner)
- `market_label`
- `option_a`
- `option_b`
- `prob_a`
- `prob_b`
- `lock_at`
- `status` (open/locked/settled)
- `result_option` (nullable)

### `user_predictions`
- `id` (PK)
- `user_id` (FK)
- `prediction_event_id` (FK)
- `selected_option`
- `potential_points`
- `status` (open/locked/settled)
- `is_correct` (nullable)
- `created_at`

### `rewards_ledger`
- `id` (PK)
- `user_id` (FK)
- `source_type` (prediction_settlement/challenge/badge)
- `points_delta`
- `coins_delta`
- `xp_delta`
- `metadata_json`
- `created_at`

---

## 4) Settlement & Locking Rules

### Locking
- Every prediction event includes `lock_at`.
- Client may edit prediction while `now < lock_at` and event is `open`.
- At/after `lock_at`, event becomes `locked` (idempotent transition).

### Settlement
- Triggered by domain events (`over_end`, `phase_end`, `match_end`).
- Resolve event result deterministically from `match_states`.
- Settle all linked `user_predictions` in one transaction.

### Reward Policy (MVP constants)
- Correct:
  - `+50` points
  - `+10` coins
  - streak bonus: `+5 * streak_current`
- Wrong:
  - `+15` XP
  - no points/coin deduction

---

## 5) Event-Driven Loop

1. `ball_update` received.
2. Match state snapshot persisted.
3. Features recalculated.
4. Model probabilities refreshed.
5. New prediction events published (or existing updated if still open).
6. Users submit/modify picks.
7. Lock job closes events at `lock_at`.
8. Settlement job resolves outcomes after trigger events.
9. Reward + gamification jobs update profile and leaderboard.
10. Dashboard cache invalidated/refreshed.

---

## 6) Recommended Tech Stack (pragmatic MVP)

- Backend: Node.js (NestJS) or Python (FastAPI)
- Stream/Queue: Kafka or Redis Streams
- DB: PostgreSQL
- Cache: Redis
- Realtime updates: WebSocket/SSE
- Model serving: Python microservice (scikit-learn / XGBoost)
- Observability: OpenTelemetry + Prometheus/Grafana

---

## 7) API Endpoints (example)

### Prediction
- `GET /matches/:id/prediction-events?status=open`
- `POST /prediction-events/:id/picks`
- `PATCH /picks/:id` (only before lock)

### Dashboard
- `GET /dashboard/me`
- `GET /leaderboard?window=daily`
- `GET /predictions/history?matchId=...`

### Admin/ops
- `POST /ops/recompute-settlement/:eventId`
- `POST /ops/rebuild-leaderboard`

---

## 8) Non-Functional Requirements

- **Fairness**: full audit trail (model output + lock timestamps + settlement inputs).
- **Latency**: target < 2s from ball event to updated prediction options.
- **Idempotency**: ingestion and settlement must be safe to replay.
- **Scalability**: shard by `match_id`; cache dashboard aggregates.
- **Security**: signed tokens, rate limits, anti-bot checks.

---

## 9) Milestones

1. **Week 1–2**: Auth/profile + match ingestion + basic dashboard.
2. **Week 3–4**: Model inference pipeline + prediction event lifecycle.
3. **Week 5**: Settlement + rewards + gamification basics.
4. **Week 6**: Leaderboard, observability, hardening, beta launch.

This plan is intentionally MVP-oriented so the startup can launch quickly and iterate model quality over time.
