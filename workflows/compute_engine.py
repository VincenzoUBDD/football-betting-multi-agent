"""
Quantitative Compute Engine — Football Betting Intelligence System.

Implements the core mathematical models:
- Poisson goal model
- Expected Goals (xG) model
- Elo rating system
- Monte Carlo simulation
- Bayesian updating
- Ensemble aggregation
- Kelly Criterion
"""

from __future__ import annotations

import math
import random
from collections import Counter
from dataclasses import dataclass, field
from typing import Optional

# ── Poisson Model ────────────────────────────────────────────────────────────


def poisson_pmf(k: int, lam: float) -> float:
    """Probability of exactly k goals given lambda."""
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return (lam ** k) * math.exp(-lam) / math.factorial(k)


def poisson_cdf(k: int, lam: float) -> float:
    """Cumulative probability of k or fewer goals."""
    return sum(poisson_pmf(i, lam) for i in range(k + 1))


def compute_lambda(
    team_avg_goals_scored: float,
    opponent_avg_goals_conceded: float,
    league_avg_goals: float,
    home_advantage_factor: float = 1.20,
    is_home: bool = True,
) -> float:
    """
    Compute expected goals (lambda) for a team.

    lambda = attack_strength * defense_weakness * home_advantage

    attack_strength = team_avg_scored / league_avg
    defense_weakness = opponent_avg_conceded / league_avg
    """
    attack_strength = team_avg_goals_scored / league_avg_goals if league_avg_goals > 0 else 1.0
    defense_weakness = opponent_avg_goals_conceded / league_avg_goals if league_avg_goals > 0 else 1.0

    lam = attack_strength * defense_weakness * league_avg_goals

    if is_home:
        lam *= home_advantage_factor

    return max(lam, 0.1)


def poisson_match_probabilities(
    lambda_home: float, lambda_away: float, max_goals: int = 10
) -> dict:
    """
    Compute match outcome probabilities using bivariate Poisson.

    Returns probabilities for home win, draw, away win, and score distribution.
    """
    home_win_prob = 0.0
    draw_prob = 0.0
    away_win_prob = 0.0
    score_probs: list[dict] = []
    over25_prob = 0.0
    btts_prob = 0.0

    for h in range(max_goals + 1):
        for a in range(max_goals + 1):
            p = poisson_pmf(h, lambda_home) * poisson_pmf(a, lambda_away)

            if h > a:
                home_win_prob += p
            elif h == a:
                draw_prob += p
            else:
                away_win_prob += p

            if h + a > 2:
                over25_prob += p

            if h > 0 and a > 0:
                btts_prob += p

            if p > 0.005:
                score_probs.append({
                    "score": f"{h}-{a}",
                    "probability": round(p, 4),
                })

    score_probs.sort(key=lambda x: x["probability"], reverse=True)

    return {
        "home_win_probability": round(home_win_prob, 4),
        "draw_probability": round(draw_prob, 4),
        "away_win_probability": round(away_win_prob, 4),
        "over25_probability": round(over25_prob, 4),
        "under25_probability": round(1 - over25_prob, 4),
        "btts_probability": round(btts_prob, 4),
        "most_likely_scores": score_probs[:10],
        "lambda_home": round(lambda_home, 4),
        "lambda_away": round(lambda_away, 4),
    }


# ── Elo Rating System ────────────────────────────────────────────────────────


@dataclass
class EloSystem:
    """Elo rating system for football teams."""

    default_rating: float = 1500.0
    k_factor: float = 32.0
    home_advantage: float = 100.0
    ratings: dict[str, float] = field(default_factory=dict)

    def get_rating(self, team: str) -> float:
        return self.ratings.get(team, self.default_rating)

    def set_rating(self, team: str, rating: float) -> None:
        self.ratings[team] = rating

    def expected_score(self, rating_a: float, rating_b: float) -> float:
        """Expected score for team A (1 = win, 0.5 = draw, 0 = loss)."""
        return 1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / 400.0))

    def win_probability(
        self, home_team: str, away_team: str, draw_adjustment: float = 0.22
    ) -> dict:
        """
        Compute Elo-based win/draw/loss probabilities.

        Accounts for home advantage and draw probability.
        """
        rating_home = self.get_rating(home_team) + self.home_advantage
        rating_away = self.get_rating(away_team)

        home_expected = self.expected_score(rating_home, rating_away)

        # Adjust for draw probability (football-specific)
        # Draw probability is highest when teams are evenly matched
        rating_diff = abs(rating_home - rating_away)
        draw_prob = draw_adjustment * math.exp(-rating_diff / 400.0)

        home_win_prob = home_expected - draw_prob * 0.5
        away_win_prob = (1 - home_expected) - draw_prob * 0.5

        # Ensure non-negative
        home_win_prob = max(home_win_prob, 0.05)
        away_win_prob = max(away_win_prob, 0.05)
        draw_prob = max(draw_prob, 0.10)

        # Normalize
        total = home_win_prob + draw_prob + away_win_prob
        return {
            "home_win_probability": round(home_win_prob / total, 4),
            "draw_probability": round(draw_prob / total, 4),
            "away_win_probability": round(away_win_prob / total, 4),
            "elo_home": round(rating_home, 0),
            "elo_away": round(rating_away, 0),
        }

    def update_ratings(
        self,
        home_team: str,
        away_team: str,
        home_goals: int,
        away_goals: int,
    ) -> None:
        """Update Elo ratings based on match result."""
        rating_home = self.get_rating(home_team) + self.home_advantage
        rating_away = self.get_rating(away_team)

        expected_home = self.expected_score(rating_home, rating_away)

        if home_goals > away_goals:
            actual_home = 1.0
        elif home_goals == away_goals:
            actual_home = 0.5
        else:
            actual_home = 0.0

        # Goal difference multiplier
        goal_diff = abs(home_goals - away_goals)
        gd_multiplier = 1.0
        if goal_diff == 2:
            gd_multiplier = 1.5
        elif goal_diff >= 3:
            gd_multiplier = (11.0 + goal_diff) / 8.0

        delta = self.k_factor * gd_multiplier * (actual_home - expected_home)

        self.ratings[home_team] = self.get_rating(home_team) + delta
        self.ratings[away_team] = self.get_rating(away_team) - delta


# ── Monte Carlo Simulation ───────────────────────────────────────────────────


def monte_carlo_simulation(
    lambda_home: float,
    lambda_away: float,
    n_simulations: int = 10_000,
    seed: Optional[int] = None,
) -> dict:
    """
    Run Monte Carlo simulation of match outcomes.

    Returns probability distribution over outcomes.
    """
    if seed is not None:
        random.seed(seed)

    results = Counter()
    total_goals: list[int] = []
    btts_count = 0

    for _ in range(n_simulations):
        home_goals = _sample_goals(lambda_home)
        away_goals = _sample_goals(lambda_away)

        if home_goals > away_goals:
            results["home_win"] += 1
        elif home_goals == away_goals:
            results["draw"] += 1
        else:
            results["away_win"] += 1

        total_goals.append(home_goals + away_goals)
        if home_goals > 0 and away_goals > 0:
            btts_count += 1

    n = float(n_simulations)

    return {
        "home_win_probability": round(results["home_win"] / n, 4),
        "draw_probability": round(results["draw"] / n, 4),
        "away_win_probability": round(results["away_win"] / n, 4),
        "over25_probability": round(sum(1 for g in total_goals if g > 2) / n, 4),
        "under25_probability": round(sum(1 for g in total_goals if g <= 2) / n, 4),
        "btts_probability": round(btts_count / n, 4),
        "avg_total_goals": round(sum(total_goals) / n, 2),
        "n_simulations": n_simulations,
    }


def _sample_goals(lam: float) -> int:
    """Sample goals from Poisson distribution."""
    if lam <= 0:
        return 0
    L = math.exp(-lam)
    k = 0
    p = 1.0
    while p > L:
        k += 1
        p *= random.random()
    return k - 1


# ── Bayesian Updating ────────────────────────────────────────────────────────


def bayesian_update(
    prior_prob: float,
    likelihood_ratio: float,
) -> float:
    """
    Update probability using Bayes' theorem.

    posterior_odds = prior_odds * likelihood_ratio
    posterior_prob = posterior_odds / (1 + posterior_odds)

    Args:
        prior_prob: Prior probability (0-1)
        likelihood_ratio: Strength of new evidence (>1 supports, <1 opposes)

    Returns:
        Updated posterior probability
    """
    if prior_prob <= 0 or prior_prob >= 1:
        return prior_prob

    prior_odds = prior_prob / (1 - prior_prob)
    posterior_odds = prior_odds * likelihood_ratio
    posterior_prob = posterior_odds / (1 + posterior_odds)

    return posterior_prob


def compute_likelihood_ratio(
    evidence_strength: float,  # 0-1 scale
    direction: str,  # "support" or "oppose"
) -> float:
    """
    Convert evidence strength to likelihood ratio.

    Strong supporting evidence → LR > 1
    Strong opposing evidence → LR < 1
    """
    if direction == "support":
        return 1.0 + evidence_strength * 2.0  # LR range: 1.0 - 3.0
    else:
        return 1.0 / (1.0 + evidence_strength * 2.0)  # LR range: 0.33 - 1.0


# ── Ensemble Aggregation ─────────────────────────────────────────────────────


def ensemble_aggregate(
    poisson_result: dict,
    elo_result: dict,
    monte_carlo_result: Optional[dict] = None,
    weights: Optional[dict] = None,
) -> dict:
    """
    Aggregate predictions from multiple models using weighted average.

    Default weights: Poisson 35%, Elo 25%, Monte Carlo 40%
    If Monte Carlo unavailable: Poisson 50%, Elo 50%
    """
    if weights is None:
        if monte_carlo_result:
            weights = {"poisson": 0.35, "elo": 0.25, "monte_carlo": 0.40}
        else:
            weights = {"poisson": 0.50, "elo": 0.50}

    models_used = ["poisson", "elo"]
    home_probs = [
        poisson_result["home_win_probability"] * weights["poisson"],
        elo_result["home_win_probability"] * weights["elo"],
    ]
    draw_probs = [
        poisson_result["draw_probability"] * weights["poisson"],
        elo_result["draw_probability"] * weights["elo"],
    ]
    away_probs = [
        poisson_result["away_win_probability"] * weights["poisson"],
        elo_result["away_win_probability"] * weights["elo"],
    ]

    if monte_carlo_result:
        models_used.append("monte_carlo")
        home_probs.append(
            monte_carlo_result["home_win_probability"] * weights["monte_carlo"]
        )
        draw_probs.append(
            monte_carlo_result["draw_probability"] * weights["monte_carlo"]
        )
        away_probs.append(
            monte_carlo_result["away_win_probability"] * weights["monte_carlo"]
        )

    weight_sum = sum(weights[m] for m in models_used)
    ensemble_home = sum(home_probs) / weight_sum
    ensemble_draw = sum(draw_probs) / weight_sum
    ensemble_away = sum(away_probs) / weight_sum

    # Normalize
    total = ensemble_home + ensemble_draw + ensemble_away
    ensemble_home /= total
    ensemble_draw /= total
    ensemble_away /= total

    # Compute model std dev
    all_home = [poisson_result["home_win_probability"], elo_result["home_win_probability"]]
    if monte_carlo_result:
        all_home.append(monte_carlo_result["home_win_probability"])

    mean_home = sum(all_home) / len(all_home)
    variance = sum((p - mean_home) ** 2 for p in all_home) / len(all_home)
    std_dev = math.sqrt(variance)

    # Aggregate over25
    over25 = poisson_result.get("over25_probability", 0.5)
    if monte_carlo_result:
        over25 = (over25 * 0.5 + monte_carlo_result.get("over25_probability", 0.5) * 0.5)

    return {
        "ensemble_home_prob": round(ensemble_home, 4),
        "ensemble_draw_prob": round(ensemble_draw, 4),
        "ensemble_away_prob": round(ensemble_away, 4),
        "over25_probability": round(over25, 4),
        "under25_probability": round(1 - over25, 4),
        "model_std_dev": round(std_dev, 4),
        "models_used": models_used,
    }


# ── Kelly Criterion ──────────────────────────────────────────────────────────


def kelly_criterion(
    estimated_prob: float,
    decimal_odds: float,
    fraction: float = 0.25,
) -> dict:
    """
    Compute Kelly Criterion stake.

    f* = (bp - q) / b
    where b = decimal_odds - 1, p = estimated prob, q = 1 - p

    Args:
        estimated_prob: Model-estimated true probability (0-1)
        decimal_odds: Available market odds
        fraction: Fraction of full Kelly to use (0.25 = quarter Kelly)

    Returns:
        Dict with full_kelly, fractional_kelly, edge_percent, recommendation
    """
    if decimal_odds <= 1.0:
        return {
            "full_kelly": 0.0,
            "fractional_kelly": 0.0,
            "edge_percent": 0.0,
            "recommendation": "INVALID_ODDS",
        }

    b = decimal_odds - 1.0
    p = estimated_prob
    q = 1.0 - p

    edge = (p * decimal_odds) - 1.0  # Expected value per unit bet

    full_kelly = (b * p - q) / b
    full_kelly = max(full_kelly, 0.0)

    fractional_kelly = full_kelly * fraction

    return {
        "full_kelly": round(full_kelly, 4),
        "fractional_kelly": round(fractional_kelly, 4),
        "edge_percent": round(edge * 100, 2),
        "recommendation": "BET" if edge > 0.03 else "MARGINAL" if edge > 0 else "NO_BET",
    }


# ── Odds Analysis Utilities ──────────────────────────────────────────────────


def implied_probability(decimal_odds: float) -> float:
    """Convert decimal odds to implied probability."""
    if decimal_odds <= 0:
        return 0.0
    return 1.0 / decimal_odds


def compute_overround(home_odds: float, draw_odds: float, away_odds: float) -> float:
    """Compute bookmaker overround."""
    return (
        implied_probability(home_odds)
        + implied_probability(draw_odds)
        + implied_probability(away_odds)
    )


def fair_probabilities(
    home_odds: float, draw_odds: float, away_odds: float
) -> dict:
    """
    Remove overround to compute fair (true) implied probabilities.
    """
    overround = compute_overround(home_odds, draw_odds, away_odds)

    return {
        "fair_home_prob": round(implied_probability(home_odds) / overround, 4),
        "fair_draw_prob": round(implied_probability(draw_odds) / overround, 4),
        "fair_away_prob": round(implied_probability(away_odds) / overround, 4),
        "overround": round(overround, 4),
    }


def detect_value(
    model_prob: float,
    market_odds: float,
    threshold: float = 0.03,
) -> dict:
    """Detect if a bet offers value relative to model probability."""
    market_implied = implied_probability(market_odds)
    edge = model_prob - market_implied
    edge_percent = (model_prob * market_odds - 1.0) * 100

    kelly = kelly_criterion(model_prob, market_odds)

    return {
        "model_probability": round(model_prob, 4),
        "market_implied_probability": round(market_implied, 4),
        "edge": round(edge, 4),
        "edge_percent": round(edge_percent, 2),
        "is_value": edge_percent > threshold * 100,
        "kelly": kelly,
    }


# ── Confidence Computation ───────────────────────────────────────────────────


def compute_confidence(
    model_consensus: float,
    market_clarity: float,
    data_quality: float,
    tactical_clarity: float,
    contradiction_penalty: float,
) -> str:
    """
    Compute confidence rating from multiple dimensions.

    Each input is 0.0–1.0. Returns S, A+, A, B+, B, C, or D.
    """
    raw_score = (
        model_consensus * 0.30
        + market_clarity * 0.25
        + data_quality * 0.20
        + tactical_clarity * 0.15
        + (1 - contradiction_penalty) * 0.10
    )

    if raw_score >= 0.92:
        return "S"
    if raw_score >= 0.82:
        return "A+"
    if raw_score >= 0.72:
        return "A"
    if raw_score >= 0.62:
        return "B+"
    if raw_score >= 0.50:
        return "B"
    if raw_score >= 0.35:
        return "C"
    return "D"


# ── League Baselines ─────────────────────────────────────────────────────────

LEAGUE_BASELINES: dict[str, dict] = {
    "PREMIER_LEAGUE": {
        "home_win_pct": 0.43,
        "draw_pct": 0.25,
        "away_win_pct": 0.32,
        "over25_pct": 0.52,
        "btts_pct": 0.55,
        "avg_goals": 2.85,
        "home_advantage_factor": 1.25,
    },
    "SERIE_A": {
        "home_win_pct": 0.40,
        "draw_pct": 0.28,
        "away_win_pct": 0.32,
        "over25_pct": 0.48,
        "btts_pct": 0.52,
        "avg_goals": 2.70,
        "home_advantage_factor": 1.20,
    },
    "BUNDESLIGA": {
        "home_win_pct": 0.45,
        "draw_pct": 0.23,
        "away_win_pct": 0.32,
        "over25_pct": 0.58,
        "btts_pct": 0.58,
        "avg_goals": 3.10,
        "home_advantage_factor": 1.30,
    },
    "LA_LIGA": {
        "home_win_pct": 0.42,
        "draw_pct": 0.26,
        "away_win_pct": 0.32,
        "over25_pct": 0.47,
        "btts_pct": 0.50,
        "avg_goals": 2.60,
        "home_advantage_factor": 1.22,
    },
    "LIGUE_1": {
        "home_win_pct": 0.41,
        "draw_pct": 0.27,
        "away_win_pct": 0.32,
        "over25_pct": 0.50,
        "btts_pct": 0.50,
        "avg_goals": 2.70,
        "home_advantage_factor": 1.18,
    },
    "EREDIVISIE": {
        "home_win_pct": 0.44,
        "draw_pct": 0.22,
        "away_win_pct": 0.34,
        "over25_pct": 0.62,
        "btts_pct": 0.60,
        "avg_goals": 3.20,
        "home_advantage_factor": 1.28,
    },
    "CHAMPIONS_LEAGUE": {
        "home_win_pct": 0.46,
        "draw_pct": 0.24,
        "away_win_pct": 0.30,
        "over25_pct": 0.55,
        "btts_pct": 0.54,
        "avg_goals": 2.90,
        "home_advantage_factor": 1.25,
    },
    "UEFA_EUROPA_LEAGUE": {
        "home_win_pct": 0.44,
        "draw_pct": 0.26,
        "away_win_pct": 0.30,
        "over25_pct": 0.54,
        "btts_pct": 0.53,
        "avg_goals": 2.80,
        "home_advantage_factor": 1.20,
    },
    "UEFA_CONFERENCE_LEAGUE": {
        "home_win_pct": 0.34,
        "draw_pct": 0.34,
        "away_win_pct": 0.32,
        "over25_pct": 0.52,
        "btts_pct": 0.50,
        "avg_goals": 2.65,
        "home_advantage_factor": 1.05,
    },
    "GENERIC": {
        "home_win_pct": 0.42,
        "draw_pct": 0.26,
        "away_win_pct": 0.32,
        "over25_pct": 0.50,
        "btts_pct": 0.52,
        "avg_goals": 2.75,
        "home_advantage_factor": 1.22,
    },
}


def get_league_baseline(league: str) -> dict:
    """Get baseline statistics for a league."""
    league_upper = league.upper().replace(" ", "_")
    return LEAGUE_BASELINES.get(league_upper, LEAGUE_BASELINES["GENERIC"])
