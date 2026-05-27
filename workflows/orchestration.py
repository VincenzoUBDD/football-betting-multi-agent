"""
Orchestration Engine — Football Betting Intelligence System.

Manages the execution order, communication, and integration of all agents.
Implements retry logic, error handling, logging, and result aggregation.
"""

from __future__ import annotations

import json
import logging
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from .models import (
    AgentOutputBase,
    ChiefAnalystAgentOutput,
    MatchContext,
    NewsAgentOutput,
    OddsAgentOutput,
    PipelineResult,
    QuantAgentOutput,
    RefereeAgentOutput,
    RiskAgentOutput,
    SentimentAgentOutput,
    SharpMoneyAgentOutput,
    TacticalAgentOutput,
    HistoricalAgentOutput,
    FinalReport,
    MatchOverview,
    MarketOddsAnalysis,
    QuantitativeProjection,
    TacticalMatchup,
    TeamNews,
    MarketSentiment,
    HistoricalAnalysis,
    RiskAssessment,
    BetRecommendation,
    FinalVerdict,
    FinalAction,
    AgentContributions,
    ConfidenceRating,
    BettingRecommendation,
)

from .compute_engine import (
    compute_lambda,
    poisson_match_probabilities,
    monte_carlo_simulation,
    ensemble_aggregate,
    fair_probabilities,
    detect_value,
    compute_confidence,
    get_league_baseline,
    EloSystem,
)

# Try importing the Odds API client (graceful fallback if SDK not installed)
try:
    from .odds_api_client import OddsAPIClientWrapper
    from odds_api.exceptions import InvalidAPIKeyError
    _ODDS_API_AVAILABLE = True
except ImportError:
    _ODDS_API_AVAILABLE = False
    OddsAPIClientWrapper = None
    InvalidAPIKeyError = Exception

# ── Logging Setup ────────────────────────────────────────────────────────────

def setup_logging(log_dir: Path) -> logging.Logger:
    """Configure logging for the orchestration system."""
    log_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("FootballBettingIntel")
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:
        fh = logging.FileHandler(
            log_dir / f"pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        )
        fh.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
        )
        fh.setFormatter(formatter)
        logger.addHandler(fh)

        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(formatter)
        logger.addHandler(ch)

    return logger


# ── Agent Runner ─────────────────────────────────────────────────────────────


class AgentRunner:
    """
    Manages the execution of a single agent.

    Handles:
    - Prompt construction
    - Execution with retry
    - Output parsing and validation
    - Error handling
    """

    MAX_RETRIES = 2

    def __init__(
        self,
        logger: logging.Logger,
        prompts_dir: Path,
        shared_rules: str = "",
    ):
        self.logger = logger
        self.prompts_dir = prompts_dir
        self.shared_rules = shared_rules

    def run_agent(
        self,
        agent_name: str,
        agent_func: Callable,
        match_context: MatchContext,
        previous_outputs: Optional[dict[str, AgentOutputBase]] = None,
    ) -> Optional[AgentOutputBase]:
        """
        Execute an agent with retry logic.

        Args:
            agent_name: Name of the agent (for logging)
            agent_func: The function that executes the agent logic
            match_context: Match context data
            previous_outputs: Outputs from previously run agents

        Returns:
            Agent output or None if all retries fail
        """
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                self.logger.info(f"[{agent_name}] Starting attempt {attempt}/{self.MAX_RETRIES}")
                start_time = time.time()

                result = agent_func(match_context, previous_outputs or {})

                elapsed = time.time() - start_time
                self.logger.info(
                    f"[{agent_name}] Completed in {elapsed:.2f}s — "
                    f"Confidence: {result.confidence}, Risk: {result.risk_level}"
                )
                return result

            except Exception as e:
                self.logger.error(
                    f"[{agent_name}] Attempt {attempt} failed: {e}\n"
                    f"{traceback.format_exc()}"
                )
                if attempt == self.MAX_RETRIES:
                    self.logger.error(f"[{agent_name}] All retries exhausted. Agent FAILED.")
                    return None
                time.sleep(1.0)

        return None


# ── Agent Implementation Functions ───────────────────────────────────────────

# ── API Integration Helper ────────────────────────────────────────────────────


def _fetch_odds_from_api(
    home_team: str,
    away_team: str,
    league: str,
    ctx: MatchContext,
) -> Optional[dict]:
    """
    Attempt to fetch live odds from The Odds API.

    Returns a dict with opening_odds, current_odds (as OpeningOdds/CurrentOdds),
    and raw analysis, or None if API is unavailable.
    """
    if not _ODDS_API_AVAILABLE:
        return None

    league_to_sport_key = {
        "PREMIER_LEAGUE": "soccer_epl",
        "SERIE_A": "soccer_italy_serie_a",
        "BUNDESLIGA": "soccer_germany_bundesliga",
        "LA_LIGA": "soccer_spain_la_liga",
        "LIGUE_1": "soccer_france_ligue_one",
        "EREDIVISIE": "soccer_netherlands_eredivisie",
        "UEFA_CHAMPIONS_LEAGUE": "soccer_uefa_champs_league",
        "UEFA_EUROPA_LEAGUE": "soccer_uefa_europa_league",
        "UEFA_CONFERENCE_LEAGUE": "soccer_uefa_europa_conference_league",
    }

    try:
        client = OddsAPIClientWrapper()
    except InvalidAPIKeyError:
        return None

    sport_key = league_to_sport_key.get(league, "soccer")

    # Find the match
    event = client.find_match(home_team, away_team, sport=sport_key, league=sport_key)
    if not event:
        # Try broader search with generic soccer key
        event = client.find_match(home_team, away_team, sport="soccer")

    if not event:
        return None

    event_id = str(event.get("id", event.get("event_id", "")))
    if not event_id:
        return None

    # Get comprehensive odds analysis
    analysis = client.get_match_odds_analysis(event_id)
    if analysis.get("error"):
        return None

    best = analysis.get("best_odds", {})
    opening = analysis.get("opening_odds", {})
    movements = analysis.get("odds_movement_detected", {})

    # Build OpeningOdds and CurrentOdds from API data
    from .models import OpeningOdds, CurrentOdds

    api_opening = OpeningOdds(
        home=opening.get("home", best.get("home", 0)) if opening else best.get("home", 0),
        draw=opening.get("draw", best.get("draw", 0)) if opening else best.get("draw", 0),
        away=opening.get("away", best.get("away", 0)) if opening else best.get("away", 0),
    )
    api_current = CurrentOdds(
        home=best.get("home", 0),
        draw=best.get("draw", 0),
        away=best.get("away", 0),
    )

    return {
        "opening": api_opening,
        "current": api_current,
        "analysis": analysis,
        "event_id": event_id,
    }


def run_odds_agent(
    ctx: MatchContext, _previous: dict
) -> OddsAgentOutput:
    """
    Odds Agent: analyzes betting odds, market movement, and bookmaker behavior.

    Attempts to fetch live odds from The Odds API first.
    Falls back to MatchContext odds or computes from baseline.
    """
    league_baseline = get_league_baseline(ctx.league)

    # Try API first
    api_data = _fetch_odds_from_api(ctx.home_team, ctx.away_team, ctx.league, ctx)
    if api_data:
        opening = api_data["opening"]
        current = api_data["current"]
        api_analysis = api_data["analysis"]
    else:
        opening = ctx.opening_odds
        current = ctx.current_odds
        api_analysis = {}

    if not opening or not current:
        return OddsAgentOutput(
            match_id=ctx.match_id,
            core_prediction="Insufficient odds data for analysis",
            confidence=ConfidenceRating.D,
            risk_level="HIGH",
            opening_odds={"home": 0, "draw": 0, "away": 0, "over_25": 0, "under_25": 0},
            current_odds={"home": 0, "draw": 0, "away": 0},
            uncertainty_notes=["No odds data provided"],
        )

    # Compute fair probabilities from current odds
    fair = fair_probabilities(current.home, current.draw, current.away)

    # Detect odds movement direction
    movements = []
    for market, open_val, curr_val in [
        ("1X2_Home", opening.home, current.home),
        ("1X2_Draw", opening.draw, current.draw),
        ("1X2_Away", opening.away, current.away),
    ]:
        if open_val and curr_val and open_val > 0:
            change_pct = (curr_val - open_val) / open_val * 100
            direction = "shortening" if change_pct < -1 else ("lengthening" if change_pct > 1 else "stable")
            movements.append({
                "market": market,
                "direction": direction,
                "magnitude": round(abs(change_pct), 2),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "interpretation": _interpret_movement(market, direction, abs(change_pct)),
            })

    # Determine market bias
    if fair["fair_home_prob"] > fair["fair_away_prob"] + 0.05:
        market_bias = "HOME"
    elif fair["fair_away_prob"] > fair["fair_home_prob"] + 0.05:
        market_bias = "AWAY"
    else:
        market_bias = "NEUTRAL"

    # Assess trap risk
    trap_risk = _assess_trap_risk(opening, current, movements)

    # Determine sharp side — prefer API detection, fallback to movement-based
    api_sharp = api_analysis.get("sharp_side", "")
    if api_sharp and api_sharp != "NONE_DETECTED":
        sharp_side = api_sharp
    else:
        sharp_side = _detect_sharp_side(movements, opening, current)

    # Build opening/closing odds objects, enriching with API data where available
    ah_line = getattr(current, "asian_handicap_line", None)
    ah_home = getattr(current, "asian_handicap_home_odds", None)
    ah_away = getattr(current, "asian_handicap_away_odds", None)

    # Enrich with API totals/spreads data
    api_totals = api_analysis.get("totals_by_bookmaker", {})
    api_spreads = api_analysis.get("spreads_by_bookmaker", {})
    over_25_from_api = None
    under_25_from_api = None
    for bk_data in api_totals.values():
        if bk_data.get("line") == 2.5:
            over_25_from_api = bk_data.get("over")
            under_25_from_api = bk_data.get("under")
            break
    if not api_spreads and api_spreads is not None:
        pass  # spreads parsed but unused in base OddsAgentOutput model

    opening_odds_data = {
        "home": opening.home, "draw": opening.draw, "away": opening.away,
        "over_25": over_25_from_api or opening.over_25 or 0,
        "under_25": under_25_from_api or opening.under_25 or 0,
        "asian_handicap_line": ah_line or opening.asian_handicap_line,
        "asian_handicap_home_odds": ah_home or opening.asian_handicap_home_odds,
        "asian_handicap_away_odds": ah_away or opening.asian_handicap_away_odds,
    }
    current_odds_data = {
        "home": current.home, "draw": current.draw, "away": current.away,
        "over_25": over_25_from_api or opening.over_25 or 0,
        "under_25": under_25_from_api or opening.under_25 or 0,
        "asian_handicap_line": ah_line or opening.asian_handicap_line,
        "asian_handicap_home_odds": ah_home or opening.asian_handicap_home_odds,
        "asian_handicap_away_odds": ah_away or opening.asian_handicap_away_odds,
    }

    # Build output
    data_source = "LIVE_API" if api_analysis else "HARDCODED"
    bookmakers_used = api_analysis.get("bookmakers_queried", "N/A") if api_analysis else "N/A"

    home_edge = fair["fair_home_prob"] - league_baseline["home_win_pct"]
    core = (
        f"Market implies {fair['fair_home_prob']:.1%} home win probability "
        f"(vs league baseline {league_baseline['home_win_pct']:.1%}). "
        f"Overround: {fair['overround']:.2%}. "
        f"Bias: {market_bias}. "
        f"Source: {data_source}"
        + (f" ({bookmakers_used})" if api_analysis else "")
        + "."
    )

    from .models import OpeningOdds, CurrentOdds, OddsMovement as OddsMovementModel

    # Build key factors enriched with API info
    key_factors = [
        f"Opening odds: {opening.home}/{opening.draw}/{opening.away}",
        f"Current odds: {current.home}/{current.draw}/{current.away}",
        f"Overround: {fair['overround']:.2%}",
        f"Market bias: {market_bias}",
    ]
    supporting_evidence = [
        f"League baseline home win rate: {league_baseline['home_win_pct']:.1%}",
        f"Fair home probability: {fair['fair_home_prob']:.1%}",
    ]

    if api_analysis:
        key_factors.append(f"Data source: LIVE (The Odds API — {bookmakers_used})")
        supporting_evidence.append(
            f"Bookmakers queried: {bookmakers_used} "
            f"({api_analysis.get('bookmakers_count', '?')} available)"
        )
        if api_analysis.get("sharp_confidence"):
            supporting_evidence.append(
                f"API sharp detection confidence: {api_analysis['sharp_confidence']}"
            )

    return OddsAgentOutput(
        match_id=ctx.match_id,
        core_prediction=core,
        confidence=ConfidenceRating.B if (trap_risk == "NONE" or api_analysis) else ConfidenceRating.C,
        risk_level="LOW" if trap_risk == "NONE" else "MEDIUM",
        opening_odds=OpeningOdds(**opening_odds_data),
        current_odds=CurrentOdds(**current_odds_data),
        odds_movement=[OddsMovementModel(**m) for m in movements],
        market_bias=market_bias,
        bookmaker_intention="GENUINE" if trap_risk == "NONE" else "SUSPICIOUS",
        trap_risk=trap_risk,
        sharp_side=sharp_side,
        overround=round(fair["overround"], 4),
        probabilities={
            "market_implied_home": fair["fair_home_prob"],
            "market_implied_draw": fair["fair_draw_prob"],
            "market_implied_away": fair["fair_away_prob"],
        },
        key_factors=key_factors,
        supporting_evidence=supporting_evidence,
    )


def _interpret_movement(market: str, direction: str, magnitude: float) -> str:
    if magnitude < 1:
        return f"{market} stable (negligible movement)"
    if direction == "shortening":
        return f"{market} shortening by {magnitude:.1f}% — increasing confidence or sharp money"
    elif direction == "lengthening":
        return f"{market} lengthening by {magnitude:.1f}% — decreasing confidence or public fade"
    return f"{market} stable"


def _assess_trap_risk(
    opening, current, movements: list
) -> str:
    """Assess whether odds pattern suggests a trap."""
    if not opening or not current:
        return "MEDIUM"

    # Check for suspicious movement against public expectations
    home_moved_against = False
    for m in movements:
        if "Home" in m["market"] and m["direction"] == "lengthening" and m["magnitude"] > 5:
            home_moved_against = True

    # If home odds lengthened significantly while being favorites → potential trap
    if (
        opening.home < opening.away
        and current.home > opening.home
        and (current.home - opening.home) / opening.home > 0.05
    ):
        return "HIGH"

    if home_moved_against:
        return "MEDIUM"

    return "LOW"


def _detect_sharp_side(movements: list, opening, current) -> str:
    """Detect which side shows sharp money characteristics."""
    shortening_signals = [m for m in movements if m["direction"] == "shortening" and m["magnitude"] > 3]

    if not shortening_signals:
        return "NONE_DETECTED"

    home_shortening = any("Home" in s["market"] for s in shortening_signals)
    away_shortening = any("Away" in s["market"] for s in shortening_signals)

    if home_shortening and not away_shortening:
        return "HOME"
    elif away_shortening and not home_shortening:
        return "AWAY"

    return "NONE_DETECTED"


def run_quant_agent(
    ctx: MatchContext, previous: dict
) -> QuantAgentOutput:
    """
    Quant Agent: runs Poisson, Elo, Monte Carlo models.
    """
    league_baseline = get_league_baseline(ctx.league)

    # Use league baselines as input when real data unavailable
    home_avg_goals = league_baseline["avg_goals"] * league_baseline["home_win_pct"] + 0.3
    away_avg_goals = league_baseline["avg_goals"] * league_baseline["away_win_pct"] + 0.2
    home_avg_conceded = league_baseline["avg_goals"] * league_baseline["away_win_pct"] + 0.2
    away_avg_conceded = league_baseline["avg_goals"] * league_baseline["home_win_pct"] + 0.3

    # Adjust using odds if available
    if previous.get("odds_agent"):
        odds_out = previous["odds_agent"]
        if hasattr(odds_out, "probabilities") and odds_out.probabilities:
            market_home = odds_out.probabilities.get("market_implied_home", 0.42)
            home_avg_goals *= (market_home / league_baseline["home_win_pct"])
            away_avg_goals *= ((1 - market_home - 0.25) / league_baseline["away_win_pct"])

    # Compute lambdas
    lambda_home = compute_lambda(
        home_avg_goals, away_avg_conceded, league_baseline["avg_goals"],
        league_baseline["home_advantage_factor"], is_home=True,
    )
    lambda_away = compute_lambda(
        away_avg_goals, home_avg_conceded, league_baseline["avg_goals"],
        league_baseline["home_advantage_factor"], is_home=False,
    )

    # Poisson model
    poisson_result = poisson_match_probabilities(lambda_home, lambda_away)

    # Elo model
    elo = EloSystem()
    elo.set_rating(ctx.home_team, 1550.0)
    elo.set_rating(ctx.away_team, 1480.0)
    elo_result = elo.win_probability(ctx.home_team, ctx.away_team)

    # Monte Carlo
    mc_result = monte_carlo_simulation(lambda_home, lambda_away, n_simulations=10_000)

    # Ensemble
    ensemble = ensemble_aggregate(poisson_result, elo_result, mc_result)

    # Detect value bets from odds
    from .models import MostLikelyScore, ValueBet, ModelDisagreement

    value_bets_list = []
    if ctx.current_odds:
        for market_name, model_prob, market_odds in [
            ("Home Win", ensemble["ensemble_home_prob"], ctx.current_odds.home),
            ("Draw", ensemble["ensemble_draw_prob"], ctx.current_odds.draw),
            ("Away Win", ensemble["ensemble_away_prob"], ctx.current_odds.away),
        ]:
            val = detect_value(model_prob, market_odds)
            if val["is_value"]:
                value_bets_list.append(
                    ValueBet(
                        market=market_name,
                        fair_odds=round(1 / model_prob, 2) if model_prob > 0 else 999,
                        market_odds=market_odds,
                        edge_percent=val["edge_percent"],
                        kelly_fraction=val["kelly"]["fractional_kelly"],
                    )
                )

    scores = [
        MostLikelyScore(**s)
        for s in poisson_result.get("most_likely_scores", [])[:5]
    ]

    # Model disagreement
    model_disagreement_list = []
    if ensemble["model_std_dev"] > 0.05:
        model_disagreement_list.append(
            ModelDisagreement(
                models=["Poisson", "Elo", "MonteCarlo"],
                discrepancy=f"Home win probability std dev: {ensemble['model_std_dev']:.3f}",
                magnitude=round(ensemble["model_std_dev"], 4),
            )
        )

    core = (
        f"Ensemble: Home {ensemble['ensemble_home_prob']:.1%} / "
        f"Draw {ensemble['ensemble_draw_prob']:.1%} / "
        f"Away {ensemble['ensemble_away_prob']:.1%}. "
        f"Expected goals: {lambda_home:.2f} — {lambda_away:.2f}. "
        f"Model std dev: {ensemble['model_std_dev']:.3f}."
    )

    return QuantAgentOutput(
        match_id=ctx.match_id,
        core_prediction=core,
        confidence=ConfidenceRating.B if ensemble["model_std_dev"] < 0.06 else ConfidenceRating.C,
        risk_level="LOW" if ensemble["model_std_dev"] < 0.04 else "MEDIUM",
        home_win_probability=ensemble["ensemble_home_prob"],
        draw_probability=ensemble["ensemble_draw_prob"],
        away_win_probability=ensemble["ensemble_away_prob"],
        expected_goals_home=round(lambda_home, 2),
        expected_goals_away=round(lambda_away, 2),
        over25_probability=ensemble["over25_probability"],
        under25_probability=ensemble["under25_probability"],
        btts_yes_probability=poisson_result.get("btts_probability", 0.5),
        most_likely_scores=scores,
        value_bets=value_bets_list,
        model_disagreement=model_disagreement_list,
        poisson_lambda_home=round(lambda_home, 4),
        poisson_lambda_away=round(lambda_away, 4),
        elo_home=elo_result.get("elo_home", 1500),
        elo_away=elo_result.get("elo_away", 1500),
        elo_win_probability=elo_result["home_win_probability"],
        probabilities={
            "ensemble_home": ensemble["ensemble_home_prob"],
            "ensemble_draw": ensemble["ensemble_draw_prob"],
            "ensemble_away": ensemble["ensemble_away_prob"],
        },
        key_factors=[
            f"Poisson lambda: {lambda_home:.2f} (home) / {lambda_away:.2f} (away)",
            f"Elo ratings: {elo_result.get('elo_home', 1500):.0f} vs {elo_result.get('elo_away', 1500):.0f}",
            f"Monte Carlo ({mc_result['n_simulations']} sims): Home {mc_result['home_win_probability']:.1%}",
            f"Model ensemble std dev: {ensemble['model_std_dev']:.3f}",
        ],
        supporting_evidence=[
            f"League baseline home win: {league_baseline['home_win_pct']:.1%}",
            f"Most likely score: {scores[0].score if scores else 'N/A'} ({scores[0].probability:.1%} probability)" if scores else "",
            f"Over 2.5 probability: {ensemble['over25_probability']:.1%}",
        ],
    )


def run_tactical_agent(
    ctx: MatchContext, _previous: dict
) -> TacticalAgentOutput:
    """Tactical Agent: analyzes formations, pressing, transitions, set pieces."""
    from .models import TacticalAdvantage, TransitionRisk, SetPieceEdge, FormationInteraction

    return TacticalAgentOutput(
        match_id=ctx.match_id,
        core_prediction="Tactical analysis requires external match data input for full accuracy.",
        confidence=ConfidenceRating.C,
        risk_level="MEDIUM",
        tactical_advantage=TacticalAdvantage.NEUTRAL,
        formation_interaction=[
            FormationInteraction(
                home_formation="4-3-3",
                away_formation="4-2-3-1",
                key_matchup_zone="Central midfield (3v2 numerical advantage home)",
                advantage="HOME",
            )
        ],
        transition_risk=TransitionRisk.MEDIUM,
        set_piece_edge=SetPieceEdge.NEUTRAL,
        probabilities={
            "tactical_edge_home": 0.52,
            "tactical_edge_away": 0.48,
        },
        key_factors=[
            "Home formation 4-3-3 creates central midfield overload vs 4-2-3-1",
            "Tactical edge: MODERATE_HOME based on formation matchup",
        ],
        uncertainty_notes=[
            "Tactical data requires external match data integration for full analysis",
            "Formation predictions based on recent patterns, may differ at kickoff",
        ],
    )


def run_news_agent(
    ctx: MatchContext, _previous: dict
) -> NewsAgentOutput:
    """News Agent: analyzes injuries, fatigue, motivation, weather."""
    from .models import (
        FatigueIndex, MotivationScore, RotationRiskAssessment,
        LockerRoomStatus, WeatherAssessment,
    )

    return NewsAgentOutput(
        match_id=ctx.match_id,
        core_prediction="News/fundamental analysis requires external data feed integration.",
        confidence=ConfidenceRating.C,
        risk_level="MEDIUM",
        fatigue_index=FatigueIndex(
            home=30.0, away=35.0, differential=5.0,
            assessment="Both teams on standard rest. Away team slightly more fatigued due to travel.",
        ),
        motivation_score=MotivationScore(
            home=70.0, away=65.0, differential=5.0,
            assessment="Standard league match motivation. Home team slightly higher.",
        ),
        rotation_risk=RotationRiskAssessment(home="LOW", away="LOW"),
        locker_room_status=LockerRoomStatus(home="STABLE", away="STABLE"),
        weather_assessment=WeatherAssessment(
            condition="Clear",
            temperature=18.0,
            wind="Light",
            impact_on_match="No significant weather impact expected",
        ),
        probabilities={
            "fundamental_home_boost": 0.02,
            "fundamental_away_boost": -0.01,
        },
        key_factors=[
            "No critical injuries or suspensions reported",
            "Standard rest period: no significant fatigue advantage",
            "Weather: ideal conditions for football",
        ],
        uncertainty_notes=[
            "Injury data requires external integration for real-time updates",
            "Late team news can change the fundamental picture significantly",
        ],
    )


def run_sentiment_agent(
    ctx: MatchContext, _previous: dict
) -> SentimentAgentOutput:
    """Sentiment Agent: analyzes public betting patterns and narrative overreactions."""
    from .models import OverreactionSignal, ContrarianOpportunity

    return SentimentAgentOutput(
        match_id=ctx.match_id,
        core_prediction="Public sentiment analysis requires external data feed integration.",
        confidence=ConfidenceRating.C,
        risk_level="MEDIUM",
        public_betting_bias="HOME",
        bet_ticket_split={"home_pct": 58, "draw_pct": 22, "away_pct": 20},
        money_volume_split={"home_pct": 52, "draw_pct": 24, "away_pct": 24},
        ticket_vs_money_divergence="Slight divergence: ticket% higher than money% on home side, suggesting small sharp interest on away/draw",
        market_sentiment="BULLISH_HOME",
        overreaction_signals=[
            OverreactionSignal(
                narrative="Home advantage overrated by public",
                assessment="Home team bias is typical; 58% ticket share within normal range",
                validity_score=0.3,
            )
        ],
        contrarian_opportunities=[],
        big_team_bias_detected=False,
        probabilities={
            "public_overreaction_risk": 0.15,
        },
        key_factors=[
            "Public slightly favoring home side (58% tickets)",
            "Money split more balanced than ticket split — mild sharp divergence",
        ],
        uncertainty_notes=[
            "Sentiment data requires external integration for real-time accuracy",
            "Social media sentiment not available without API integration",
        ],
    )


def run_historical_agent(
    ctx: MatchContext, _previous: dict
) -> HistoricalAgentOutput:
    """Historical Agent: analyzes H2H, similar-odds patterns, referee history."""
    from .models import HistoricalMatchup, SimilarOddsOutcome, RefereeProfile

    league_baseline = get_league_baseline(ctx.league)

    return HistoricalAgentOutput(
        match_id=ctx.match_id,
        core_prediction="Historical analysis requires database integration for full accuracy.",
        confidence=ConfidenceRating.C,
        risk_level="MEDIUM",
        h2h_summary={
            "total_matches": "Insufficient data",
            "sample_quality": "LOW — requires database integration",
        },
        similar_odds_outcomes=[
            SimilarOddsOutcome(
                odds_range="Home 1.80-1.90 / Draw 3.40-3.60 / Away 4.00-4.50",
                sample_size=0,
                home_win_pct=0.48,
                draw_pct=0.26,
                away_win_pct=0.26,
                comparison_to_market="Estimated from league baseline — actual sample requires database",
            )
        ],
        league_baseline_context={
            "home_win_base": league_baseline["home_win_pct"],
            "draw_base": league_baseline["draw_pct"],
            "over25_base": league_baseline["over25_pct"],
            "btts_base": league_baseline["btts_pct"],
            "avg_goals": league_baseline["avg_goals"],
        },
        probabilities={
            "historical_home_advantage": league_baseline["home_win_pct"],
        },
        key_factors=[
            f"League baseline: Home wins {league_baseline['home_win_pct']:.1%} of matches",
            f"League average goals: {league_baseline['avg_goals']:.2f}",
        ],
        uncertainty_notes=[
            "Historical database requires integration for full analysis",
            "H2H records not available without database connection",
        ],
    )


def run_referee_agent(
    ctx: MatchContext, _previous: dict
) -> RefereeAgentOutput:
    """Referee Agent: analyzes referee tendencies and impact on match dynamics."""
    return RefereeAgentOutput(
        match_id=ctx.match_id,
        core_prediction="Referee analysis requires external data integration for specific official data.",
        confidence=ConfidenceRating.C,
        risk_level="LOW",
        referee_profile={
            "avg_yellows": 3.8,
            "avg_reds": 0.18,
            "penalty_rate": 0.22,
            "league_comparison": "Near league average",
        },
        card_market_implication={
            "direction": "NEUTRAL",
            "confidence": "LOW",
            "recommended_market": "Insufficient data for recommendation",
        },
        penalty_probability_adjustment={
            "baseline": 0.22,
            "adjusted": 0.22,
            "delta": 0.0,
        },
        home_bias_index=0.05,
        style_interaction_assessment={
            "home_team_impact": "MINIMAL",
            "away_team_impact": "MINIMAL",
            "net_effect": "NEUTRAL",
        },
        probabilities={
            "over_cards_prob": 0.50,
            "under_cards_prob": 0.50,
            "penalty_awarded_prob": 0.22,
            "red_card_prob": 0.18,
        },
        key_factors=[
            "Referee identity not specified — using league average profile",
            "Card market: NEUTRAL outlook based on league averages",
        ],
        uncertainty_notes=[
            "Referee assignment data requires external integration",
            "VAR availability varies by competition",
        ],
    )


def run_sharp_money_agent(
    ctx: MatchContext, previous: dict
) -> SharpMoneyAgentOutput:
    """Sharp Money Agent: detects professional betting activity and steam moves."""
    from .models import SteamSignal, RLMSignal, BookmakerSpecific

    # Use odds movement data from Odds Agent if available
    sharp_signals = []
    rlm_signals = []
    sharp_detected = False
    sharp_side = "NONE_DETECTED"

    if previous.get("odds_agent"):
        odds_out = previous["odds_agent"]
        if hasattr(odds_out, "odds_movement"):
            for m in odds_out.odds_movement:
                if hasattr(m, "direction") and m.direction == "shortening" and hasattr(m, "magnitude") and m.magnitude > 3:
                    sharp_signals.append(
                        SteamSignal(
                            timestamp=m.timestamp if hasattr(m, "timestamp") else "",
                            books_affected=["Pinnacle", "Bet365"],
                            magnitude=m.magnitude,
                            steam_score=60.0,
                            interpretation=f"Odds shortening suggests buying pressure on {m.market}",
                        )
                    )
                    sharp_detected = True

    if sharp_detected:
        shortening_markets = [s for s in sharp_signals if hasattr(s, "interpretation") and "Home" in str(s.interpretation)]
        if shortening_markets:
            sharp_side = "HOME"

    return SharpMoneyAgentOutput(
        match_id=ctx.match_id,
        core_prediction="Sharp money analysis requires live market data feed for full accuracy.",
        confidence=ConfidenceRating.C if not sharp_detected else ConfidenceRating.B,
        risk_level="MEDIUM",
        sharp_money_detected=sharp_detected,
        sharp_side=sharp_side,
        steam_signals=sharp_signals,
        bookmaker_specific=BookmakerSpecific(
            pinnacle_signal="No significant Pinnacle-specific signal detected",
            asian_consensus="No Asian book consensus data available",
        ),
        exchange_analysis={
            "back_volume_side": "N/A",
            "lay_volume_side": "N/A",
            "interpretation": "Exchange data requires API integration",
        },
        sharp_confidence=45.0 if sharp_detected else 15.0,
        clv_assessment={
            "market_efficiency_grade": "MODERATE",
            "expected_clv": "Unknown without historical data",
        },
        probabilities={
            "sharp_on_home": 0.55 if sharp_side == "HOME" else 0.35,
        },
        key_factors=(
            [f"Detected {len(sharp_signals)} potential sharp money signals"]
            if sharp_signals
            else ["No clear sharp money signals detected"]
        ),
        uncertainty_notes=[
            "Real-time market data required for accurate sharp money detection",
            "Pinnacle movement tracking requires API integration",
        ],
    )


def run_risk_agent(
    ctx: MatchContext, previous: dict
) -> RiskAgentOutput:
    """
    Risk Agent: THE HIGHEST PRIORITY agent.
    Verifies consistency, assesses risk, and makes final betting decision.
    """
    from .models import ModelConflict, UncertaintyFactor, StakeSuggestion, EdgeConfidenceInterval

    conflicts = []
    uncertainty_factors = []
    consistency_scores = []

    # Check Quant vs Odds consistency
    odds_agent = previous.get("odds_agent")
    quant_agent = previous.get("quant_agent")

    if odds_agent and quant_agent:
        if (
            hasattr(odds_agent, "probabilities")
            and hasattr(quant_agent, "home_win_probability")
        ):
            market_home = odds_agent.probabilities.get("market_implied_home", 0)
            model_home = quant_agent.home_win_probability
            diff = abs(market_home - model_home)

            if diff > 0.08:
                conflicts.append(
                    ModelConflict(
                        agents_in_conflict=["OddsAgent", "QuantModelAgent"],
                        conflict_description=(
                            f"Market implies {market_home:.1%} home win; "
                            f"model estimates {model_home:.1%}. "
                            f"Difference: {diff:.1%}"
                        ),
                        severity="MAJOR" if diff > 0.12 else "MODERATE",
                        resolution_possible=True,
                    )
                )
                consistency_scores.append(0.3 if diff > 0.12 else 0.6)
            else:
                consistency_scores.append(0.9)

    # Check for data quality issues
    data_quality = 0.6  # Base: moderate (external data feeds not integrated)
    if not ctx.opening_odds:
        data_quality = 0.3
        uncertainty_factors.append(
            UncertaintyFactor(
                factor="Missing odds data",
                impact="HIGH",
                mitigation="Integrate odds API feed",
            )
        )

    # Compute overall scores
    agent_consistency = (
        sum(consistency_scores) / len(consistency_scores)
        if consistency_scores
        else 0.5
    )
    info_completeness = data_quality
    volatility = 0.35  # Standard league match

    # Determine betting recommendation
    betting_rec = BettingRecommendation.NO_BET
    stake_pct = 0.0
    no_bet_reason = ""

    if info_completeness < 0.4:
        betting_rec = BettingRecommendation.NO_BET
        no_bet_reason = "Insufficient data quality. Integrate odds data feeds."
    elif volatility > 0.7:
        betting_rec = BettingRecommendation.NO_BET
        no_bet_reason = "Extreme volatility detected."
    elif any(c.severity in ("CRITICAL", "MAJOR") for c in conflicts):
        betting_rec = BettingRecommendation.NO_BET
        no_bet_reason = f"Significant model conflicts: {len([c for c in conflicts if c.severity in ('CRITICAL', 'MAJOR')])} major disagreement(s)."
    elif agent_consistency > 0.75 and info_completeness > 0.6:
        betting_rec = BettingRecommendation.TRACK_ONLY
        stake_pct = 0.0
        no_bet_reason = "System operating without live data feeds. TRACK ONLY recommended until integrations are active."
    else:
        betting_rec = BettingRecommendation.TRACK_ONLY
        no_bet_reason = "Marginal conditions for betting. Paper trade for validation."

    # Overall risk
    if volatility > 0.6 or agent_consistency < 0.4:
        overall_risk = "HIGH"
    elif volatility > 0.4 or agent_consistency < 0.6:
        overall_risk = "MEDIUM"
    else:
        overall_risk = "LOW"

    return RiskAgentOutput(
        match_id=ctx.match_id,
        core_prediction=f"Risk assessment: {overall_risk} risk. Recommendation: {betting_rec.value}. {no_bet_reason}",
        confidence=ConfidenceRating.D if betting_rec == BettingRecommendation.NO_BET else ConfidenceRating.C,
        risk_level=overall_risk,
        overall_risk_level=overall_risk,
        volatility_score=volatility,
        model_conflict=conflicts,
        high_uncertainty_factors=uncertainty_factors,
        betting_recommendation=betting_rec,
        stake_suggestion=StakeSuggestion(
            max_stake_percent=stake_pct,
            kelly_fraction=0.0,
            stop_loss_triggers=[
                "Data quality below threshold",
                "Major agent disagreement",
                "Odds move >5% against position pre-match",
            ],
        ),
        agent_consistency_score=round(agent_consistency, 2),
        info_completeness_score=round(info_completeness, 2),
        edge_confidence_interval=EdgeConfidenceInterval(
            lower_bound=-0.02,
            upper_bound=0.05,
            confidence_level=0.95,
        ),
        probabilities={
            "risk_weighted_home": quant_agent.home_win_probability * 0.95 if quant_agent else 0.40,
            "risk_weighted_draw": quant_agent.draw_probability if quant_agent else 0.26,
            "risk_weighted_away": quant_agent.away_win_probability * 1.02 if quant_agent else 0.34,
        },
        key_factors=[
            f"Agent consistency score: {agent_consistency:.2f}",
            f"Information completeness: {info_completeness:.2f}",
            f"Volatility score: {volatility:.2f}",
            f"Conflicts detected: {len(conflicts)}",
        ],
        uncertainty_notes=[
            "System operating without live data feeds — all outputs are demo/skeleton",
            "Production deployment requires odds API, xG data, injury feeds",
        ],
    )


# ── 竞彩 (China Sports Lottery) Mapping ──────────────────────────────────


def _generate_jingcai_recommendations(
    quant,
    odds,
    ctx: MatchContext,
    league_baseline: dict,
) -> list[dict]:
    """
    Map quantitative model output to China Sports Lottery (竞彩) compatible
    betting recommendations.

    竞彩 available markets (and what's NOT available):
      - 胜平负 (1X2)
      - 让球胜平负 (integer handicaps only: -1, -2, +1, +2)
      - 总进球数 (0, 1, 2, 3, 4, 5, 6, 7+)
      - 比分 (correct score)
      - 半全场 (HT/FT result)

    NOT available in 竞彩:
      - Under/Over X.5
      - BTTS
      - Asian Handicap (non-integer)
      - Double Chance (X2)
      - Win to Nil
    """
    jc_recs = []

    if not quant:
        return jc_recs

    # ── Aggregate exact score probabilities into total-goal buckets ──────
    goal_bucket_probs = {str(i): 0.0 for i in range(8)}  # 0..7
    goal_bucket_probs["7+"] = 0.0
    if quant.most_likely_scores:
        for s in quant.most_likely_scores:
            try:
                parts = s.score.split("-")
                total = int(parts[0]) + int(parts[1])
                key = str(total) if total < 7 else "7+"
                goal_bucket_probs[key] += s.probability
            except (ValueError, IndexError):
                continue

    # Sort goal buckets by probability
    ranked_goals = sorted(
        [(k, v) for k, v in goal_bucket_probs.items() if v > 0],
        key=lambda x: x[1],
        reverse=True,
    )

    # ── Determine which total-goal buckets to recommend ──────────────────
    # Combine adjacent high-probability buckets
    recommended_goals = []
    cumulative_goal_prob = 0.0
    for goal_count, prob in ranked_goals:
        if cumulative_goal_prob < 0.70 and prob > 0.05:
            recommended_goals.append(goal_count)
            cumulative_goal_prob += prob

    # Sort numerically for display
    def _goal_sort_key(g):
        if g == "7+":
            return 7
        return int(g)

    recommended_goals.sort(key=_goal_sort_key)

    # ── 1. 总进球数 recommendation ──────────────────────────────────────
    if recommended_goals:
        top_goals = recommended_goals[:3]  # max 3 selections for practicality
        total_goal_prob = sum(goal_bucket_probs.get(g, 0) for g in top_goals)
        jc_recs.append({
            "market": "总进球数",
            "selection": " + ".join(f"{g}球" for g in top_goals),
            "model_probability": round(total_goal_prob, 3),
            "rationale": (
                f"模型最可能比分对应总进球 {'/'.join(top_goals)}，"
                f"累积概率 {total_goal_prob:.1%}"
            ),
            "confidence": "A" if total_goal_prob > 0.60 else ("B+" if total_goal_prob > 0.50 else "B"),
            "single_pick": top_goals[0] if len(top_goals) == 1 else None,
        })

    # ── 2. 胜平负 recommendation ────────────────────────────────────────
    home_p = quant.home_win_probability
    draw_p = quant.draw_probability
    away_p = quant.away_win_probability

    # Find the highest-probability 1X2 outcome
    outcomes_1x2 = [
        ("主胜", home_p, getattr(odds, "current_odds", None)),
        ("平局", draw_p, None),
        ("客胜", away_p, None),
    ]
    outcomes_1x2.sort(key=lambda x: x[1], reverse=True)

    top_1x2 = outcomes_1x2[0]
    if top_1x2[1] > 0.35:
        jc_recs.append({
            "market": "胜平负",
            "selection": top_1x2[0],
            "model_probability": round(top_1x2[1], 3),
            "rationale": f"模型{'/'.join(o[0] for o in outcomes_1x2[:2])}概率最高",
            "confidence": "A" if top_1x2[1] > 0.50 else ("B+" if top_1x2[1] > 0.40 else "B"),
            "single_pick": top_1x2[0],
        })

    # ── 3. 让球胜平负 recommendation ────────────────────────────────────
    # Use actual 竞彩 handicap lines if provided, otherwise auto-estimate
    handicap_lines = ctx.jingcai_handicaps or _determine_jingcai_handicaps(
        home_p, draw_p, away_p, league_baseline
    )
    for hline in handicap_lines:
        hcp_rec = _build_jingcai_handicap_rec(
            hline, home_p, draw_p, away_p, ctx
        )
        if hcp_rec:
            jc_recs.append(hcp_rec)

    # ── 4. 比分 recommendation ──────────────────────────────────────────
    if quant.most_likely_scores:
        top_scores = quant.most_likely_scores[:3]
        score_str = " / ".join(s.score for s in top_scores)
        score_prob = sum(s.probability for s in top_scores)
        jc_recs.append({
            "market": "比分",
            "selection": score_str,
            "model_probability": round(score_prob, 3),
            "rationale": (
                f"模型前三最可能比分，累积概率 {score_prob:.1%}"
            ),
            "confidence": "B+" if score_prob > 0.30 else "B",
            "single_pick": top_scores[0].score,
        })

    # Sort by confidence
    conf_order = {"A": 0, "A-": 1, "B+": 2, "B": 3, "B-": 4, "C": 5}
    jc_recs.sort(key=lambda r: conf_order.get(r.get("confidence", "C"), 99))

    return jc_recs


def _determine_jingcai_handicaps(
    home_p: float,
    draw_p: float,
    away_p: float,
    baseline: dict,
) -> list[str]:
    """
    Determine the likely 竞彩 integer handicap lines for this match.

    竞彩 integer handicaps: -3, -2, -1, +1, +2, +3.
    Returns all handicap lines that could plausibly be offered,
    sorted by relevance (most likely first).

    Logic: the wider the gap between home/away probabilities, the
    larger the handicap line 竞彩 will set.
    """
    gap = home_p - away_p
    lines: list[str] = []

    if gap > 0.50:
        # Dominant home favorite — 竞彩 likely offers -2 and -1
        lines = ["-2", "-1"]
    elif gap > 0.60:
        lines = ["-3", "-2", "-1"]
    elif gap > 0.25:
        lines = ["-1"]
        if gap > 0.40:
            lines.append("-2")
    elif gap > 0.05:
        lines = ["-1"]
    elif gap > -0.05:
        # Near-even
        if home_p > away_p:
            lines = ["-1"]
        else:
            lines = ["+1"]
    elif gap > -0.25:
        lines = ["+1"]
    elif gap > -0.40:
        lines = ["+1", "+2"]
    elif gap > -0.50:
        lines = ["+1", "+2"]
    else:
        lines = ["+2", "+1"]
        if gap < -0.60:
            lines = ["+3", "+2", "+1"]

    return lines


def _build_jingcai_handicap_rec(
    handicap_line: str,
    home_p: float,
    draw_p: float,
    away_p: float,
    ctx: MatchContext,
) -> Optional[dict]:
    """Build a 让球胜平负 recommendation dict for any integer handicap."""
    hcp_int = int(handicap_line)
    margin = abs(hcp_int) + 1  # goals needed to "cover": -1 needs 2+, -2 needs 3+

    # Fraction of favored-team wins that cover vs land exactly on the line.
    # Larger margins → smaller fractions (exponentially decaying).
    _cover_factor = {2: 0.35, 3: 0.15, 4: 0.05}  # win by N+ goals
    _exact_factor = {2: 0.30, 3: 0.13, 4: 0.04}  # win by exactly N goals

    if hcp_int < 0:  # Home gives handicap, e.g., -1, -2
        required = margin  # home must win by 'required' goals for 让胜
        cf = _cover_factor.get(required, 0.03)
        ef = _exact_factor.get(required, 0.02)

        home_cover = home_p * cf       # 让胜: home wins by required+
        home_exact = home_p * ef       # 让平: home wins by exactly required
        non_cover = away_p + draw_p + (home_p * (1 - cf - ef))  # 让负

        total = home_cover + home_exact + non_cover
        if total <= 0:
            return None

        rang_sheng = home_cover / total
        rang_ping = home_exact / total
        rang_fu = non_cover / total

        sides = [
            ("让胜", rang_sheng),
            ("让平", rang_ping),
            ("让负", rang_fu),
        ]
        sides.sort(key=lambda x: x[1], reverse=True)

        if sides[0][0] == "让负":
            selection = f"让负 + 让平 (双选)"
            combined_prob = rang_fu + rang_ping
            rationale = (
                f"模型{ctx.home_team}让{hcp_int}球下，"
                f"不让球胜概率{rang_fu:.1%}，让平概率{rang_ping:.1%}，"
                f"双选覆盖 {combined_prob:.1%}"
            )
            primary = "让负+让平"
        elif sides[0][0] == "让胜" and sides[0][1] > 0.45:
            selection = f"让胜 (单挑)"
            combined_prob = rang_sheng
            rationale = (
                f"模型{ctx.home_team}让{hcp_int}球下，"
                f"净胜{required}+球概率{rang_sheng:.1%}，可单挑"
            )
            primary = "让胜"
        else:
            selection = f"让负 + 让平 (双选)"
            combined_prob = rang_fu + rang_ping
            rationale = (
                f"模型{ctx.home_team}让{hcp_int}球下，"
                f"不让球胜概率{rang_fu:.1%}，让平概率{rang_ping:.1%}，"
                f"双选覆盖 {combined_prob:.1%}"
            )
            primary = "让负+让平"

        confidence = "A-" if combined_prob > 0.75 else ("B+" if combined_prob > 0.60 else "B")

    else:  # Away gives handicap, e.g., +1, +2 (home receives +hcp_int)
        required = margin
        cf = _cover_factor.get(required, 0.03)
        ef = _exact_factor.get(required, 0.02)

        away_cover = away_p * cf
        away_exact = away_p * ef
        home_not_lose_by_required = home_p + draw_p + (away_p * (1 - cf - ef))

        total = home_not_lose_by_required + away_exact + away_cover
        if total <= 0:
            return None

        rang_sheng = home_not_lose_by_required / total  # 让胜: home doesn't lose by required+
        rang_ping = away_exact / total                     # 让平: home loses by exactly required
        rang_fu = away_cover / total                      # 让负: home loses by required+

        sides = [
            ("让胜", rang_sheng),
            ("让平", rang_ping),
            ("让负", rang_fu),
        ]
        sides.sort(key=lambda x: x[1], reverse=True)

        return {
            "market": "让球胜平负",
            "handicap_line": handicap_line,
            "selection": f"{sides[0][0]} (单挑)" if sides[0][1] > 0.50 else f"{' / '.join(s[0] for s in sides[:2])} (双选)",
            "primary_pick": sides[0][0],
            "model_probability": round(sides[0][1], 3),
            "rationale": (
                f"模型{ctx.away_team}客胜概率仅{away_p:.1%}，"
                f"{ctx.home_team}受让{abs(hcp_int)}球下让胜概率{sides[0][1]:.1%}"
            ),
            "confidence": "A-" if sides[0][1] > 0.55 else ("B+" if sides[0][1] > 0.45 else "B"),
        }

    return {
        "market": "让球胜平负",
        "handicap_line": handicap_line,
        "selection": selection,
        "primary_pick": primary,
        "model_probability": round(combined_prob, 3),
        "rationale": rationale,
        "confidence": confidence,
    }


# ── Chief Analyst / Final Integration ────────────────────────────────────────


def run_chief_analyst(
    ctx: MatchContext, previous: dict
) -> ChiefAnalystAgentOutput:
    """
    Chief Analyst: synthesizes all sub-agent outputs into the final report.
    """
    risk: RiskAgentOutput = previous.get("risk_agent")
    quant: Optional[QuantAgentOutput] = previous.get("quant_agent")
    odds: Optional[OddsAgentOutput] = previous.get("odds_agent")
    tactical: Optional[TacticalAgentOutput] = previous.get("tactical_agent")
    news: Optional[NewsAgentOutput] = previous.get("news_agent")
    sentiment: Optional[SentimentAgentOutput] = previous.get("sentiment_agent")
    historical: Optional[HistoricalAgentOutput] = previous.get("historical_agent")
    referee: Optional[RefereeAgentOutput] = previous.get("referee_agent")
    sharp: Optional[SharpMoneyAgentOutput] = previous.get("sharp_money_agent")

    # Build Match Overview
    match_overview = MatchOverview(
        home_team=ctx.home_team,
        away_team=ctx.away_team,
        league=ctx.league,
        kickoff=ctx.kickoff or "TBD",
        competition_level=ctx.competition_level,
        venue=ctx.venue,
        weather_forecast=(
            news.weather_assessment.condition
            if news and news.weather_assessment
            else None
        ),
    )

    # Build Market Odds Analysis
    market_odds = MarketOddsAnalysis(
        best_odds=(
            {
                "home": odds.current_odds.home,
                "draw": odds.current_odds.draw,
                "away": odds.current_odds.away,
            }
            if odds and odds.current_odds
            else {}
        ),
        market_consensus=(
            odds.market_bias if odds else "Unknown"
        ),
        odds_movement_summary=(
            f"{len(odds.odds_movement)} movements tracked"
            if odds
            else "No odds data"
        ),
        sharp_money_indication=(
            sharp.sharp_side if sharp else "Unknown"
        ),
        trap_risk=(
            odds.trap_risk if odds else "Unknown"
        ),
    )

    # Build Quantitative Projection
    quant_proj = QuantitativeProjection(
        ensemble_home_prob=quant.home_win_probability if quant else 0.42,
        ensemble_draw_prob=quant.draw_probability if quant else 0.26,
        ensemble_away_prob=quant.away_win_probability if quant else 0.32,
        expected_goals_total=(
            (quant.expected_goals_home + quant.expected_goals_away)
            if quant
            else None
        ),
        most_likely_score=(
            quant.most_likely_scores[0].score
            if quant and quant.most_likely_scores
            else None
        ),
        value_bets_identified=(
            [vb.market for vb in quant.value_bets]
            if quant
            else []
        ),
        model_std_dev=(
            quant.model_disagreement[0].magnitude
            if quant and quant.model_disagreement
            else None
        ),
    )

    # Build Tactical Matchup
    tactical_matchup = TacticalMatchup(
        advantage=(
            tactical.tactical_advantage if tactical else "Unknown"
        ),
        key_battle=(
            tactical.formation_interaction[0].key_matchup_zone
            if tactical and tactical.formation_interaction
            else None
        ),
        predicted_tempo=(
            tactical.tempo_prediction.expected_tempo
            if tactical and tactical.tempo_prediction
            else None
        ),
        goal_impact="NEUTRAL",
    )

    # Build Team News
    team_news = TeamNews(
        critical_absences=(
            [f"{inj.player} ({inj.team})" for inj in news.injuries]
            if news
            else []
        ),
        fatigue_assessment=(
            news.fatigue_index.assessment
            if news and news.fatigue_index
            else None
        ),
        motivation_score=(
            news.motivation_score.assessment
            if news and news.motivation_score
            else None
        ),
        rotation_risk=(
            f"Home: {news.rotation_risk.home}, Away: {news.rotation_risk.away}"
            if news and news.rotation_risk
            else None
        ),
    )

    # Build Market Sentiment
    market_sent = MarketSentiment(
        public_bias=(
            sentiment.public_betting_bias if sentiment else None
        ),
        contrarian_signal=(
            len(sentiment.contrarian_opportunities) > 0
            if sentiment
            else False
        ),
        overheating_warning=(
            "Public heavy on home side"
            if sentiment
            and hasattr(sentiment, "bet_ticket_split")
            and sentiment.bet_ticket_split.get("home_pct", 0) > 65
            else None
        ),
    )

    # Build Historical Analysis
    hist_analysis = HistoricalAnalysis(
        h2h_summary=(
            historical.h2h_summary.get("sample_quality", "Unknown")
            if historical
            else None
        ),
        similar_odds_pattern=(
            f"Home win rate ~{historical.similar_odds_outcomes[0].home_win_pct:.0%}"
            if historical and historical.similar_odds_outcomes
            else None
        ),
        referee_impact=(
            referee.style_interaction_assessment.get("net_effect", "Unknown")
            if referee
            else None
        ),
    )

    # Build Risk Assessment
    risk_assess = RiskAssessment(
        overall_risk=risk.overall_risk_level if risk else "MEDIUM",
        volatility=f"{risk.volatility_score:.0%}" if risk else None,
        model_conflicts=(
            [c.conflict_description for c in risk.model_conflict]
            if risk
            else []
        ),
        betting_recommendation=(
            risk.betting_recommendation.value if risk else "NO_BET"
        ),
        stake_suggestion=(
            f"{risk.stake_suggestion.max_stake_percent:.1%} of bankroll"
            if risk and risk.stake_suggestion
            else None
        ),
        no_bet_reason=(
            risk.key_factors[0] if risk and risk.key_factors else None
        ),
    )

    # Build Betting Recommendations (international markets)
    bet_recs = []
    if quant and quant.value_bets and risk and risk.betting_recommendation not in (
        BettingRecommendation.NO_BET,
        BettingRecommendation.AVOID,
    ):
        for vb in quant.value_bets[:3]:
            bet_recs.append(
                BetRecommendation(
                    market=vb.market,
                    selection=vb.market,
                    odds=vb.market_odds,
                    stake_percent=round(vb.kelly_fraction or 0, 3),
                    rationale=f"Model edge: {vb.edge_percent:.1f}%",
                    expected_value=vb.edge_percent / 100,
                )
            )

    # Build 竞彩 (China Sports Lottery) recommendations
    jingcai_recs = []
    if quant and odds:
        lb = get_league_baseline(ctx.league)
        jingcai_recs = _generate_jingcai_recommendations(quant, odds, ctx, lb)

    # Determine final verdict
    final_action = FinalAction.NO_BET
    final_summary = ""
    if risk and risk.betting_recommendation == BettingRecommendation.NO_BET:
        final_action = FinalAction.NO_BET
        final_summary = "NO BET — system operating in demo mode without live data feeds. Production deployment with integrated odds/xG/injury APIs required before live betting recommendations."
    elif risk and risk.betting_recommendation in (
        BettingRecommendation.TRACK_ONLY,
        BettingRecommendation.CONDITIONAL,
    ):
        final_action = FinalAction.TRACK
        final_summary = "TRACK ONLY — paper trade for system validation. Insufficient data quality for live betting."
    elif bet_recs:
        final_action = FinalAction.BET
        final_summary = f"Bet recommended: {len(bet_recs)} position(s) identified."

    # Build agent contributions
    contributions = AgentContributions(
        odds_agent_key=odds.core_prediction[:100] if odds else None,
        quant_agent_key=quant.core_prediction[:100] if quant else None,
        tactical_agent_key=tactical.core_prediction[:100] if tactical else None,
        news_agent_key=news.core_prediction[:100] if news else None,
        sentiment_agent_key=sentiment.core_prediction[:100] if sentiment else None,
        historical_agent_key=historical.core_prediction[:100] if historical else None,
        risk_agent_key=risk.core_prediction[:100] if risk else None,
        referee_agent_key=referee.core_prediction[:100] if referee else None,
        sharp_money_agent_key=sharp.core_prediction[:100] if sharp else None,
    )

    final_report = FinalReport(
        match_id=ctx.match_id,
        match_overview=match_overview,
        market_odds_analysis=market_odds,
        quantitative_projection=quant_proj,
        tactical_matchup=tactical_matchup,
        team_news=team_news,
        market_sentiment=market_sent,
        historical_analysis=hist_analysis,
        risk_assessment=risk_assess,
        betting_recommendation=bet_recs,
        jingcai_recommendation=jingcai_recs,
        confidence_rating=ConfidenceRating.C,
        final_verdict=FinalVerdict(
            action=final_action,
            summary=final_summary,
            primary_recommendation="TRACK ONLY — Deploy with live data feeds for production betting recommendations.",
        ),
        agent_contributions=contributions,
    )

    return ChiefAnalystAgentOutput(
        match_id=ctx.match_id,
        core_prediction=final_summary,
        confidence=ConfidenceRating.C,
        risk_level=risk.overall_risk_level if risk else "MEDIUM",
        probabilities=quant_proj.model_dump() if quant else {},
        key_factors=[
            "System operating in demo mode",
            "All agents executed successfully",
            "Production deployment requires API integrations",
        ],
        final_report=final_report,
        uncertainty_notes=[
            "All outputs generated without live data feeds",
            "Confidence and stake recommendations are placeholder values",
        ],
    )


# ── Main Orchestrator ────────────────────────────────────────────────────────


class Orchestrator:
    """
    Main orchestrator for the Football Betting Intelligence System.

    Manages the execution pipeline, agent ordering, data flow,
    and final report generation.
    """

    AGENT_EXECUTION_ORDER = [
        ("news_agent", run_news_agent),
        ("odds_agent", run_odds_agent),
        ("quant_agent", run_quant_agent),
        ("tactical_agent", run_tactical_agent),
        ("historical_agent", run_historical_agent),
        ("sentiment_agent", run_sentiment_agent),
        ("referee_agent", run_referee_agent),
        ("sharp_money_agent", run_sharp_money_agent),
        ("risk_agent", run_risk_agent),
    ]

    def __init__(
        self,
        prompts_dir: Optional[Path] = None,
        log_dir: Optional[Path] = None,
    ):
        base = Path(__file__).resolve().parent.parent
        self.prompts_dir = prompts_dir or (base / "prompts")
        self.log_dir = log_dir or (base / "outputs" / "logs")

        self.logger = setup_logging(self.log_dir)

        # Load shared rules
        shared_rules_path = self.prompts_dir / "shared_rules.md"
        self.shared_rules = ""
        if shared_rules_path.exists():
            self.shared_rules = shared_rules_path.read_text(encoding="utf-8")
            self.logger.info(f"Loaded shared rules ({len(self.shared_rules)} chars)")

        self.runner = AgentRunner(self.logger, self.prompts_dir, self.shared_rules)

        self.logger.info("Orchestrator initialized. Ready for match analysis.")

    def run_pipeline(self, match_context: MatchContext) -> PipelineResult:
        """
        Execute the full analysis pipeline for a match.

        Args:
            match_context: Match information including odds data

        Returns:
            PipelineResult with all agent outputs and final report
        """
        start_time = time.time()
        self.logger.info(f"{'='*60}")
        self.logger.info(
            f"Pipeline START: {match_context.home_team} vs {match_context.away_team} "
            f"({match_context.league}) — Match ID: {match_context.match_id}"
        )
        self.logger.info(f"{'='*60}")

        agent_outputs: dict[str, AgentOutputBase] = {}
        agents_executed: list[str] = []
        agents_failed: list[str] = []
        errors: list[str] = []
        warnings: list[str] = []

        # Execute agents in order
        for agent_name, agent_func in self.AGENT_EXECUTION_ORDER:
            result = self.runner.run_agent(
                agent_name, agent_func, match_context, agent_outputs
            )

            if result is not None:
                agent_outputs[agent_name] = result
                agents_executed.append(agent_name)
            else:
                agents_failed.append(agent_name)
                errors.append(f"Agent {agent_name} failed after {self.runner.MAX_RETRIES} retries")
                warnings.append(f"Agent {agent_name} failed — pipeline continuing without its output")

        # Run Chief Analyst
        chief_result = self.runner.run_agent(
            "chief_analyst", run_chief_analyst, match_context, agent_outputs
        )

        if chief_result and chief_result.final_report:
            agents_executed.append("chief_analyst")
            final_report = chief_result.final_report
        else:
            agents_failed.append("chief_analyst")
            errors.append("Chief Analyst failed — no final report generated")
            final_report = None

        elapsed = time.time() - start_time
        status = (
            "SUCCESS"
            if len(agents_failed) == 0
            else ("PARTIAL" if len(agents_executed) >= 5 else "FAILED")
        )

        self.logger.info(f"{'='*60}")
        self.logger.info(
            f"Pipeline COMPLETE: {status} — "
            f"{len(agents_executed)}/{len(agents_executed) + len(agents_failed)} agents executed "
            f"in {elapsed:.1f}s"
        )
        if agents_failed:
            self.logger.warning(f"Failed agents: {', '.join(agents_failed)}")
        self.logger.info(f"{'='*60}")

        return PipelineResult(
            match_id=match_context.match_id,
            status=status,
            agents_executed=agents_executed,
            agents_failed=agents_failed,
            execution_time_seconds=round(elapsed, 2),
            final_report=final_report,
            error_log=errors,
            warnings=warnings,
        )

    def generate_markdown_report(self, report: FinalReport) -> str:
        """Generate a professional Markdown report from the FinalReport model."""
        md = []

        # Header
        md.append(f"# Football Betting Analysis Report")
        md.append(f"**Report ID:** {report.report_id} | **Match ID:** {report.match_id}")
        md.append(f"**Generated:** {report.timestamp}")
        md.append("")
        md.append("---")
        md.append("")

        # Match Overview
        mo = report.match_overview
        md.append("## Match Overview")
        md.append("")
        md.append(f"| Field | Value |")
        md.append(f"|-------|-------|")
        md.append(f"| **Home Team** | {mo.home_team} |")
        md.append(f"| **Away Team** | {mo.away_team} |")
        md.append(f"| **League** | {mo.league} |")
        md.append(f"| **Competition** | {mo.competition_level} |")
        md.append(f"| **Kickoff** | {mo.kickoff} |")
        if mo.venue:
            md.append(f"| **Venue** | {mo.venue} |")
        if mo.weather_forecast:
            md.append(f"| **Weather** | {mo.weather_forecast} |")
        md.append("")

        # Market Odds Analysis
        md.append("## Market Odds Analysis")
        md.append("")
        mao = report.market_odds_analysis
        if mao.best_odds:
            md.append("### Current Best Odds (1X2)")
            md.append("")
            md.append(f"| Home | Draw | Away |")
            md.append(f"|------|------|------|")
            h = mao.best_odds.get("home", "-")
            d = mao.best_odds.get("draw", "-")
            a = mao.best_odds.get("away", "-")
            md.append(f"| {h} | {d} | {a} |")
            md.append("")
        md.append(f"**Market Consensus:** {mao.market_consensus}")
        md.append(f"**Odds Movement:** {mao.odds_movement_summary}")
        if mao.sharp_money_indication:
            md.append(f"**Sharp Money Indication:** {mao.sharp_money_indication}")
        if mao.trap_risk:
            md.append(f"**Trap Risk:** {mao.trap_risk}")
        md.append("")

        # Quantitative Projection
        md.append("## Quantitative Model Projection")
        md.append("")
        qp = report.quantitative_projection
        md.append("### Ensemble Probabilities")
        md.append("")
        md.append(f"| Outcome | Probability |")
        md.append(f"|---------|-------------|")
        md.append(f"| **Home Win** | {qp.ensemble_home_prob:.1%} |")
        md.append(f"| **Draw** | {qp.ensemble_draw_prob:.1%} |")
        md.append(f"| **Away Win** | {qp.ensemble_away_prob:.1%} |")
        md.append("")
        if qp.expected_goals_total:
            md.append(f"**Expected Total Goals:** {qp.expected_goals_total:.2f}")
        if qp.most_likely_score:
            md.append(f"**Most Likely Score:** {qp.most_likely_score}")
        if qp.model_std_dev is not None:
            md.append(f"**Model Std Dev:** {qp.model_std_dev:.3f}")
        if qp.value_bets_identified:
            md.append(f"**Value Bets Identified:** {', '.join(qp.value_bets_identified)}")
        md.append("")

        # Tactical Matchup
        md.append("## Tactical Matchup")
        md.append("")
        tm = report.tactical_matchup
        if tm.advantage:
            md.append(f"- **Advantage:** {tm.advantage}")
        if tm.key_battle:
            md.append(f"- **Key Battle:** {tm.key_battle}")
        if tm.predicted_tempo:
            md.append(f"- **Predicted Tempo:** {tm.predicted_tempo}")
        if tm.goal_impact:
            md.append(f"- **Goal Impact:** {tm.goal_impact}")
        md.append("")

        # Team News
        md.append("## Team News & Availability")
        md.append("")
        tn = report.team_news
        if tn.critical_absences:
            md.append("### Critical Absences")
            for absence in tn.critical_absences:
                md.append(f"- {absence}")
            md.append("")
        if tn.fatigue_assessment:
            md.append(f"**Fatigue:** {tn.fatigue_assessment}")
        if tn.motivation_score:
            md.append(f"**Motivation:** {tn.motivation_score}")
        if tn.rotation_risk:
            md.append(f"**Rotation Risk:** {tn.rotation_risk}")
        md.append("")

        # Market Sentiment
        md.append("## Market Sentiment")
        md.append("")
        ms = report.market_sentiment
        if ms.public_bias:
            md.append(f"- **Public Bias:** {ms.public_bias}")
        md.append(f"- **Contrarian Signal:** {'YES' if ms.contrarian_signal else 'NO'}")
        if ms.overheating_warning:
            md.append(f"- **Warning:** {ms.overheating_warning}")
        md.append("")

        # Historical Analysis
        md.append("## Historical Pattern Analysis")
        md.append("")
        ha = report.historical_analysis
        if ha.h2h_summary:
            md.append(f"- **H2H:** {ha.h2h_summary}")
        if ha.similar_odds_pattern:
            md.append(f"- **Similar Odds:** {ha.similar_odds_pattern}")
        if ha.referee_impact:
            md.append(f"- **Referee Impact:** {ha.referee_impact}")
        md.append("")

        # Risk Assessment
        md.append("## Risk Assessment")
        md.append("")
        ra = report.risk_assessment
        md.append(f"| Metric | Value |")
        md.append(f"|--------|-------|")
        md.append(f"| **Overall Risk** | {ra.overall_risk} |")
        if ra.volatility:
            md.append(f"| **Volatility** | {ra.volatility} |")
        md.append(f"| **Recommendation** | {ra.betting_recommendation} |")
        if ra.stake_suggestion:
            md.append(f"| **Stake** | {ra.stake_suggestion} |")
        md.append("")
        if ra.model_conflicts:
            md.append("### Model Conflicts")
            for conflict in ra.model_conflicts:
                md.append(f"- {conflict}")
            md.append("")
        if ra.no_bet_reason:
            md.append(f"**Note:** {ra.no_bet_reason}")
            md.append("")

        # Betting Recommendation
        md.append("## Betting Recommendation")
        md.append("")
        if report.betting_recommendation:
            md.append(f"| # | Market | Selection | Odds | Stake % | Rationale |")
            md.append(f"|---|--------|-----------|------|---------|-----------|")
            for i, rec in enumerate(report.betting_recommendation, 1):
                md.append(
                    f"| {i} | {rec.market} | {rec.selection} | "
                    f"{rec.odds:.2f} | {rec.stake_percent:.1%} | {rec.rationale} |"
                )
        else:
            md.append("*No betting recommendations at this time.*")
        md.append("")

        # 竞彩 (China Sports Lottery) Recommendation
        if report.jingcai_recommendation:
            md.append("## 竞彩推荐 (China Sports Lottery)")
            md.append("")
            md.append("> 以下推荐已适配中国体育彩票竞彩足球玩法。")
            md.append("> 竞彩不支持 Under/Over X.5、BTTS、亚盘非整数让球、双重机会(X2) 等玩法。")
            md.append("")
            md.append("| # | 玩法 | 选项 | 模型概率 | 信心 | 说明 |")
            md.append("|---|------|------|:--:|:--:|------|")
            for i, jr in enumerate(report.jingcai_recommendation, 1):
                hcp_line = jr.get("handicap_line", "")
                market_display = (
                    f"{jr['market']} ({hcp_line})" if hcp_line
                    else jr["market"]
                )
                select = jr.get("selection", "")
                if jr.get("single_pick"):
                    select += f"  (首选: {jr['single_pick']})"
                prob = jr.get("model_probability", 0)
                conf = jr.get("confidence", "")
                rationale = jr.get("rationale", "")
                md.append(
                    f"| {i} | **{market_display}** | {select} | "
                    f"{prob:.1%} | {conf} | {rationale} |"
                )
            md.append("")
            md.append("*竞彩投注请以中国体育彩票官方实时赔率为准。*")
            md.append("")

        # Confidence Rating
        md.append(f"## Confidence Rating: **{report.confidence_rating.value}**")
        md.append("")
        confidence_descriptions = {
            "S": "Elite — Multi-model strong consensus + clear market mispricing",
            "A+": "Very High — Core logic highly consistent across agents",
            "A": "High — Strong signal, moderate uncertainty on one dimension",
            "B+": "Above Average — Clear edge but meaningful uncertainty",
            "B": "Average — Some edge suggested, conflicting signals present",
            "C": "Weak — Market appears efficient, marginal edge",
            "D": "Avoid — High uncertainty or conflicting data",
        }
        md.append(
            f"*{confidence_descriptions.get(report.confidence_rating.value, '')}*"
        )
        md.append("")

        # Final Verdict
        md.append("---")
        md.append("")
        md.append(f"## Final Verdict: **{report.final_verdict.action.value}**")
        md.append("")
        md.append(f"> {report.final_verdict.summary}")
        md.append("")
        if report.final_verdict.primary_recommendation:
            md.append(f"**Recommendation:** {report.final_verdict.primary_recommendation}")
            md.append("")
        md.append(f"*{report.final_verdict.risk_disclaimer}*")
        md.append("")

        # Agent Contributions
        md.append("---")
        md.append("")
        md.append("## Agent Contributions Summary")
        md.append("")
        ac = report.agent_contributions
        agent_keys = [
            ("Odds Agent", ac.odds_agent_key),
            ("Quant Agent", ac.quant_agent_key),
            ("Tactical Agent", ac.tactical_agent_key),
            ("News Agent", ac.news_agent_key),
            ("Sentiment Agent", ac.sentiment_agent_key),
            ("Historical Agent", ac.historical_agent_key),
            ("Referee Agent", ac.referee_agent_key),
            ("Sharp Money Agent", ac.sharp_money_agent_key),
            ("Risk Agent", ac.risk_agent_key),
        ]
        for agent_name, key in agent_keys:
            if key:
                md.append(f"- **{agent_name}:** {key}")
        md.append("")

        md.append("---")
        md.append("*Report generated by Football Betting Intelligence Multi-Agent System v1.0*")

        return "\n".join(md)
