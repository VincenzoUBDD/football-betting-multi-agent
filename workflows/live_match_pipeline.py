"""
Live / In-Play Match Pipeline — Football Betting Intelligence System.

Handles real-time match analysis for in-play betting opportunities.
Currently a structural skeleton — designed for future real-time data integration.

Key differences from pre-match:
- Uses live in-play odds instead of pre-match closing odds
- Incorporates live match state (score, time elapsed, possession, shots)
- Updates probabilities dynamically using Bayesian methods
- Tracks momentum via xG timeline
- Suspends betting during high-volatility events (goals, red cards, penalties)
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .compute_engine import (
    poisson_match_probabilities,
    bayesian_update,
    compute_likelihood_ratio,
    compute_lambda,
    get_league_baseline,
    implied_probability,
    kelly_criterion,
    detect_value,
)


class LiveMatchState:
    """
    Represents the current state of a live football match.
    """

    def __init__(
        self,
        match_id: str,
        home_team: str,
        away_team: str,
        league: str,
    ):
        self.match_id = match_id
        self.home_team = home_team
        self.away_team = away_team
        self.league = league

        # Match state
        self.minute: int = 0
        self.home_score: int = 0
        self.away_score: int = 0
        self.is_halftime: bool = False
        self.is_fulltime: bool = False
        self.injury_time: int = 0

        # Live stats
        self.home_possession: float = 50.0
        self.away_possession: float = 50.0
        self.home_shots: int = 0
        self.away_shots: int = 0
        self.home_shots_on_target: int = 0
        self.away_shots_on_target: int = 0
        self.home_corners: int = 0
        self.away_corners: int = 0
        self.home_red_cards: int = 0
        self.away_red_cards: int = 0

        # Live odds
        self.live_home_odds: Optional[float] = None
        self.live_draw_odds: Optional[float] = None
        self.live_away_odds: Optional[float] = None
        self.live_over_odds: Optional[float] = None
        self.live_under_odds: Optional[float] = None

        # Pre-match reference
        self.pre_match_home_prob: float = 0.42
        self.pre_match_draw_prob: float = 0.26
        self.pre_match_away_prob: float = 0.32
        self.pre_match_total_goals_exp: float = 2.75

        # Derived state
        self.remaining_minutes: int = 90
        self.goals_so_far: int = 0

    @property
    def is_suspended(self) -> bool:
        """Check if betting should be suspended (goal just scored, red card, etc.)"""
        return False  # Placeholder for future event detection

    @property
    def current_minute_display(self) -> str:
        if self.is_halftime:
            return "HT"
        if self.is_fulltime:
            return "FT"
        base = f"{self.minute}'"
        if self.injury_time > 0:
            base += f"+{self.injury_time}"
        return base


class LiveMatchAnalyzer:
    """
    Analyzes in-play betting opportunities during a live match.

    This is a structural skeleton. Full implementation requires:
    - Real-time odds API feed
    - Live match statistics API
    - Event-driven state updates
    """

    def __init__(self, match_state: LiveMatchState):
        self.state = match_state
        self.league_baseline = get_league_baseline(match_state.league)

        # Event log
        self.events: list[dict] = []
        self.analysis_snapshots: list[dict] = []

    def update_state(self, **kwargs) -> None:
        """Update match state with new data."""
        for key, value in kwargs.items():
            if hasattr(self.state, key):
                setattr(self.state, key, value)

        self.state.remaining_minutes = max(0, 90 - self.state.minute)
        self.state.goals_so_far = self.state.home_score + self.state.away_score

    def compute_live_probabilities(self) -> dict:
        """
        Compute updated probabilities based on live match state.

        Uses Bayesian updating from pre-match probabilities,
        adjusted for elapsed time, current score, and red cards.
        """
        remaining = self.state.remaining_minutes
        total = 90.0
        time_fraction = remaining / total if total > 0 else 0

        # Scale expected goals by remaining time
        goals_remaining_home = (
            self.state.pre_match_home_prob
            * self.league_baseline["avg_goals"]
            * time_fraction
        )
        goals_remaining_away = (
            self.state.pre_match_away_prob
            * self.league_baseline["avg_goals"]
            * time_fraction
        )

        # Adjust for red cards
        if self.state.home_red_cards > 0:
            goals_remaining_home *= 0.65
            goals_remaining_away *= 1.15
        if self.state.away_red_cards > 0:
            goals_remaining_away *= 0.65
            goals_remaining_home *= 1.15

        # Adjust for current score (teams leading may play more defensively)
        score_diff = self.state.home_score - self.state.away_score
        if score_diff > 0:
            goals_remaining_home *= 0.85
            goals_remaining_away *= 1.10
        elif score_diff < 0:
            goals_remaining_home *= 1.10
            goals_remaining_away *= 0.85

        # Run Poisson with remaining expected goals
        result = poisson_match_probabilities(
            max(goals_remaining_home, 0.05),
            max(goals_remaining_away, 0.05),
        )

        # Adjust for current score state
        current_home = self.state.home_score
        current_away = self.state.away_score

        # Compute full-time outcome probabilities
        full_time = {"home_win": 0.0, "draw": 0.0, "away_win": 0.0}

        for s in result.get("most_likely_scores", []):
            score_str = s["score"]
            prob = s["probability"]
            parts = score_str.split("-")
            remaining_h = int(parts[0])
            remaining_a = int(parts[1])
            final_h = current_home + remaining_h
            final_a = current_away + remaining_a

            if final_h > final_a:
                full_time["home_win"] += prob
            elif final_h == final_a:
                full_time["draw"] += prob
            else:
                full_time["away_win"] += prob

        return {
            "live_home_prob": round(full_time["home_win"], 4),
            "live_draw_prob": round(full_time["draw"], 4),
            "live_away_prob": round(full_time["away_win"], 4),
            "goals_remaining_home": round(goals_remaining_home, 2),
            "goals_remaining_away": round(goals_remaining_away, 2),
            "total_goals_expected": round(
                self.state.goals_so_far + goals_remaining_home + goals_remaining_away, 2
            ),
            "time_remaining": self.state.remaining_minutes,
            "current_score": f"{current_home}-{current_away}",
        }

    def find_live_value(self, live_probs: dict) -> list[dict]:
        """Identify live betting value opportunities."""
        opportunities = []

        if self.state.live_home_odds:
            val = detect_value(live_probs["live_home_prob"], self.state.live_home_odds)
            if val["is_value"]:
                opportunities.append({
                    "market": "Home Win (Live)",
                    "probability": live_probs["live_home_prob"],
                    "odds": self.state.live_home_odds,
                    "edge": val["edge_percent"],
                    "kelly": kelly_criterion(
                        live_probs["live_home_prob"], self.state.live_home_odds
                    ),
                })

        if self.state.live_draw_odds:
            val = detect_value(live_probs["live_draw_prob"], self.state.live_draw_odds)
            if val["is_value"]:
                opportunities.append({
                    "market": "Draw (Live)",
                    "probability": live_probs["live_draw_prob"],
                    "odds": self.state.live_draw_odds,
                    "edge": val["edge_percent"],
                })

        if self.state.live_away_odds:
            val = detect_value(live_probs["live_away_prob"], self.state.live_away_odds)
            if val["is_value"]:
                opportunities.append({
                    "market": "Away Win (Live)",
                    "probability": live_probs["live_away_prob"],
                    "odds": self.state.live_away_odds,
                    "edge": val["edge_percent"],
                })

        return opportunities

    def should_bet_now(self) -> dict:
        """
        Determine if now is a good time to place a live bet.

        Returns recommendation with reasoning.
        """
        if self.state.is_suspended:
            return {
                "recommendation": "WAIT",
                "reason": "Market suspended — likely goal or major event just occurred",
            }

        if self.state.remaining_minutes < 5:
            return {
                "recommendation": "NO_BET",
                "reason": "Too little time remaining for reliable analysis",
            }

        if self.state.remaining_minutes > 85:
            return {
                "recommendation": "CAUTION",
                "reason": "Late stage — high volatility, odds move rapidly",
            }

        return {
            "recommendation": "ANALYZE",
            "reason": "Market stable — analyze for value",
        }

    def take_snapshot(self) -> dict:
        """Record current state for post-match analysis."""
        probs = self.compute_live_probabilities()
        opportunities = self.find_live_value(probs)
        bet_now = self.should_bet_now()

        snapshot = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "minute": self.state.current_minute_display,
            "score": f"{self.state.home_score}-{self.state.away_score}",
            "probabilities": probs,
            "opportunities": opportunities,
            "bet_now": bet_now,
        }

        self.analysis_snapshots.append(snapshot)
        return snapshot


class LiveMatchPipeline:
    """
    Live match analysis pipeline.

    Designed to run on a polling interval during live matches.
    Currently a skeleton — production use requires:
    - Live odds data feed
    - Live match statistics API
    - WebSocket or polling infrastructure
    """

    def __init__(self, output_dir: Optional[Path] = None):
        base = Path(__file__).resolve().parent.parent
        self.output_dir = output_dir or (base / "outputs" / "live_logs")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def create_match_tracker(
        self,
        match_id: str,
        home_team: str,
        away_team: str,
        league: str = "PREMIER_LEAGUE",
        pre_match_home_prob: float = 0.42,
        pre_match_draw_prob: float = 0.26,
        pre_match_away_prob: float = 0.32,
    ) -> LiveMatchAnalyzer:
        """Create a new live match tracker."""
        state = LiveMatchState(match_id, home_team, away_team, league)
        state.pre_match_home_prob = pre_match_home_prob
        state.pre_match_draw_prob = pre_match_draw_prob
        state.pre_match_away_prob = pre_match_away_prob

        return LiveMatchAnalyzer(state)

    def log_snapshot(self, analyzer: LiveMatchAnalyzer) -> Path:
        """Save current analysis snapshot to disk."""
        snapshot = analyzer.take_snapshot()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = self.output_dir / f"{analyzer.state.match_id}_{timestamp}.json"
        path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
        return path
