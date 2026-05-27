"""
Pydantic models for the Football Betting Intelligence System.
All agent outputs and the final report are validated against these models.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ── Enums ────────────────────────────────────────────────────────────────────

class ConfidenceRating(str, Enum):
    S = "S"
    A_PLUS = "A+"
    A = "A"
    B_PLUS = "B+"
    B = "B"
    C = "C"
    D = "D"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    EXTREME = "EXTREME"


class MarketBias(str, Enum):
    HOME = "HOME"
    AWAY = "AWAY"
    DRAW = "DRAW"
    OVER = "OVER"
    UNDER = "UNDER"
    NEUTRAL = "NEUTRAL"


class TrapRisk(str, Enum):
    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class SharpSide(str, Enum):
    HOME = "HOME"
    AWAY = "AWAY"
    OVER = "OVER"
    UNDER = "UNDER"
    NONE_DETECTED = "NONE_DETECTED"


class TacticalAdvantage(str, Enum):
    STRONG_HOME = "STRONG_HOME"
    MODERATE_HOME = "MODERATE_HOME"
    NEUTRAL = "NEUTRAL"
    MODERATE_AWAY = "MODERATE_AWAY"
    STRONG_AWAY = "STRONG_AWAY"


class Tempo(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"


class TransitionRisk(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class SetPieceEdge(str, Enum):
    HOME = "HOME"
    AWAY = "AWAY"
    NEUTRAL = "NEUTRAL"


class BettingRecommendation(str, Enum):
    RECOMMENDED = "RECOMMENDED"
    CONDITIONAL = "CONDITIONAL"
    HEDGE_ONLY = "HEDGE_ONLY"
    TRACK_ONLY = "TRACK_ONLY"
    NO_BET = "NO_BET"
    AVOID = "AVOID"


class FinalAction(str, Enum):
    BET = "BET"
    NO_BET = "NO_BET"
    TRACK = "TRACK"
    HEDGE = "HEDGE"


class ConflictSeverity(str, Enum):
    MINOR = "MINOR"
    MODERATE = "MODERATE"
    MAJOR = "MAJOR"
    CRITICAL = "CRITICAL"


class UncertaintyImpact(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


# ── Base Models ──────────────────────────────────────────────────────────────

class AgentOutputBase(BaseModel):
    """Base fields every agent must include."""
    agent_name: str
    match_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    core_prediction: str
    probabilities: dict = Field(default_factory=dict)
    confidence: ConfidenceRating
    risk_level: RiskLevel
    key_factors: list[str] = Field(default_factory=list)
    supporting_evidence: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    market_implications: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    avoid_signals: list[str] = Field(default_factory=list)
    uncertainty_notes: list[str] = Field(default_factory=list)


# ── Odds Agent Models ────────────────────────────────────────────────────────

class OpeningOdds(BaseModel):
    home: float
    draw: float
    away: float
    over_25: Optional[float] = None
    under_25: Optional[float] = None
    asian_handicap_line: Optional[float] = None
    asian_handicap_home_odds: Optional[float] = None
    asian_handicap_away_odds: Optional[float] = None


class CurrentOdds(BaseModel):
    home: float
    draw: float
    away: float
    over_25: Optional[float] = None
    under_25: Optional[float] = None
    asian_handicap_line: Optional[float] = None
    asian_handicap_home_odds: Optional[float] = None
    asian_handicap_away_odds: Optional[float] = None


class OddsMovement(BaseModel):
    market: str
    direction: str
    magnitude: float
    timestamp: str
    interpretation: Optional[str] = None


class OddsAgentOutput(AgentOutputBase):
    agent_name: str = "OddsAgent"
    opening_odds: OpeningOdds
    current_odds: CurrentOdds
    odds_movement: list[OddsMovement] = Field(default_factory=list)
    market_bias: MarketBias = MarketBias.NEUTRAL
    bookmaker_intention: str = "GENUINE"
    trap_risk: TrapRisk = TrapRisk.NONE
    sharp_side: SharpSide = SharpSide.NONE_DETECTED
    overround: Optional[float] = None
    kelly_index: Optional[float] = None


# ── Quant Agent Models ───────────────────────────────────────────────────────

class MostLikelyScore(BaseModel):
    score: str
    probability: float


class ValueBet(BaseModel):
    market: str
    fair_odds: float
    market_odds: float
    edge_percent: float
    kelly_fraction: Optional[float] = None


class ModelDisagreement(BaseModel):
    models: list[str]
    discrepancy: str
    magnitude: float


class QuantAgentOutput(AgentOutputBase):
    agent_name: str = "QuantModelAgent"
    home_win_probability: float
    draw_probability: float
    away_win_probability: float
    expected_goals_home: float
    expected_goals_away: float
    over25_probability: Optional[float] = None
    under25_probability: Optional[float] = None
    btts_yes_probability: Optional[float] = None
    most_likely_scores: list[MostLikelyScore] = Field(default_factory=list)
    value_bets: list[ValueBet] = Field(default_factory=list)
    model_disagreement: list[ModelDisagreement] = Field(default_factory=list)
    poisson_lambda_home: Optional[float] = None
    poisson_lambda_away: Optional[float] = None
    elo_home: Optional[float] = None
    elo_away: Optional[float] = None
    elo_win_probability: Optional[float] = None
    xg_home_season_avg: Optional[float] = None
    xg_away_season_avg: Optional[float] = None
    xg_home_season_avg_conceded: Optional[float] = None
    xg_away_season_avg_conceded: Optional[float] = None


# ── Tactical Agent Models ────────────────────────────────────────────────────

class PossessionSplit(BaseModel):
    home: float
    away: float


class TempoPrediction(BaseModel):
    expected_tempo: Tempo = Tempo.MEDIUM
    possession_split: Optional[PossessionSplit] = None


class PressingMatchup(BaseModel):
    home_pressing_style: Optional[str] = None
    away_pressing_style: Optional[str] = None
    advantage: Optional[str] = None


class FormationInteraction(BaseModel):
    home_formation: str
    away_formation: str
    key_matchup_zone: str
    advantage: str


class TacticalAgentOutput(AgentOutputBase):
    agent_name: str = "TacticalAgent"
    tactical_advantage: TacticalAdvantage = TacticalAdvantage.NEUTRAL
    tempo_prediction: Optional[TempoPrediction] = None
    pressing_matchup: Optional[PressingMatchup] = None
    transition_risk: TransitionRisk = TransitionRisk.MEDIUM
    set_piece_edge: SetPieceEdge = SetPieceEdge.NEUTRAL
    formation_interaction: list[FormationInteraction] = Field(default_factory=list)


# ── News Agent Models ────────────────────────────────────────────────────────

class Injury(BaseModel):
    player: str
    team: str
    position: str
    tier: int
    quantified_impact: str
    status: str


class FatigueIndex(BaseModel):
    home: float
    away: float
    differential: float
    assessment: str


class MotivationScore(BaseModel):
    home: float
    away: float
    differential: float
    assessment: str


class RotationRiskAssessment(BaseModel):
    home: str
    away: str


class LockerRoomStatus(BaseModel):
    home: str
    away: str


class WeatherAssessment(BaseModel):
    condition: str
    temperature: Optional[float] = None
    wind: Optional[str] = None
    impact_on_match: str


class NewsAgentOutput(AgentOutputBase):
    agent_name: str = "NewsAgent"
    injuries: list[Injury] = Field(default_factory=list)
    suspensions: list[dict] = Field(default_factory=list)
    fatigue_index: Optional[FatigueIndex] = None
    motivation_score: Optional[MotivationScore] = None
    rotation_risk: Optional[RotationRiskAssessment] = None
    locker_room_status: Optional[LockerRoomStatus] = None
    weather_assessment: Optional[WeatherAssessment] = None
    net_fundamental_impact: Optional[str] = None


# ── Sentiment Agent Models ───────────────────────────────────────────────────

class OverreactionSignal(BaseModel):
    narrative: str
    assessment: str
    validity_score: float


class ContrarianOpportunity(BaseModel):
    market: str
    rationale: str
    contrarian_score: float


class SentimentAgentOutput(AgentOutputBase):
    agent_name: str = "SentimentAgent"
    public_betting_bias: str = "NEUTRAL"
    bet_ticket_split: dict = Field(default_factory=dict)
    money_volume_split: dict = Field(default_factory=dict)
    ticket_vs_money_divergence: Optional[str] = None
    overreaction_signals: list[OverreactionSignal] = Field(default_factory=list)
    market_sentiment: str = "NEUTRAL"
    contrarian_opportunities: list[ContrarianOpportunity] = Field(default_factory=list)
    big_team_bias_detected: bool = False
    affected_team: Optional[str] = None
    social_media_summary: dict = Field(default_factory=dict)


# ── Historical Agent Models ──────────────────────────────────────────────────

class HistoricalMatchup(BaseModel):
    date: str
    home: str
    away: str
    score: str
    odds_context: Optional[str] = None
    notes: Optional[str] = None


class SimilarOddsOutcome(BaseModel):
    odds_range: str
    sample_size: int
    home_win_pct: float
    draw_pct: float
    away_win_pct: float
    comparison_to_market: str


class RefereeProfile(BaseModel):
    name: str
    avg_yellows: float
    avg_reds: float
    penalty_rate: float
    home_win_bias: Optional[str] = None
    o25_rate: Optional[float] = None


class HistoricalAgentOutput(AgentOutputBase):
    agent_name: str = "HistoricalAgent"
    historical_matchups: list[HistoricalMatchup] = Field(default_factory=list)
    h2h_summary: dict = Field(default_factory=dict)
    similar_odds_outcomes: list[SimilarOddsOutcome] = Field(default_factory=list)
    historical_cover_rate: dict = Field(default_factory=dict)
    referee_profile: Optional[RefereeProfile] = None
    league_baseline_context: dict = Field(default_factory=dict)
    historical_anomalies: list[dict] = Field(default_factory=list)


# ── Referee Agent Models ─────────────────────────────────────────────────────

class RefereeAgentOutput(AgentOutputBase):
    agent_name: str = "RefereeAgent"
    referee_name: Optional[str] = None
    referee_profile: dict = Field(default_factory=dict)
    card_market_implication: dict = Field(default_factory=dict)
    penalty_probability_adjustment: dict = Field(default_factory=dict)
    home_bias_index: float = 0.0
    style_interaction_assessment: dict = Field(default_factory=dict)
    var_impact: Optional[str] = None
    historical_with_teams: list[dict] = Field(default_factory=list)


# ── Sharp Money Agent Models ─────────────────────────────────────────────────

class SteamSignal(BaseModel):
    timestamp: str
    books_affected: list[str]
    magnitude: float
    steam_score: float
    interpretation: str


class RLMSignal(BaseModel):
    market: str
    public_side: str
    odds_direction: str
    rlm_strength: str


class BookmakerSpecific(BaseModel):
    pinnacle_signal: Optional[str] = None
    bet365_signal: Optional[str] = None
    asian_consensus: Optional[str] = None
    exchange_signal: Optional[str] = None


class SharpMoneyAgentOutput(AgentOutputBase):
    agent_name: str = "SharpMoneyAgent"
    sharp_money_detected: bool = False
    sharp_side: SharpSide = SharpSide.NONE_DETECTED
    steam_signals: list[SteamSignal] = Field(default_factory=list)
    rlm_signals: list[RLMSignal] = Field(default_factory=list)
    bookmaker_specific: Optional[BookmakerSpecific] = None
    exchange_analysis: dict = Field(default_factory=dict)
    sharp_confidence: float = 0.0
    clv_assessment: dict = Field(default_factory=dict)
    syndicate_indicators: list[dict] = Field(default_factory=list)


# ── Risk Agent Models ────────────────────────────────────────────────────────

class ModelConflict(BaseModel):
    agents_in_conflict: list[str]
    conflict_description: str
    severity: ConflictSeverity = ConflictSeverity.MODERATE
    resolution_possible: bool = True


class UncertaintyFactor(BaseModel):
    factor: str
    impact: UncertaintyImpact = UncertaintyImpact.MEDIUM
    mitigation: Optional[str] = None


class StakeSuggestion(BaseModel):
    max_stake_percent: float = 0.0
    kelly_fraction: float = 0.0
    stop_loss_triggers: list[str] = Field(default_factory=list)


class EdgeConfidenceInterval(BaseModel):
    lower_bound: float
    upper_bound: float
    confidence_level: float = 0.95


class RiskAgentOutput(AgentOutputBase):
    agent_name: str = "RiskAgent"
    overall_risk_level: RiskLevel = RiskLevel.MEDIUM
    volatility_score: float = 0.5
    model_conflict: list[ModelConflict] = Field(default_factory=list)
    high_uncertainty_factors: list[UncertaintyFactor] = Field(default_factory=list)
    betting_recommendation: BettingRecommendation = BettingRecommendation.NO_BET
    stake_suggestion: Optional[StakeSuggestion] = None
    agent_consistency_score: float = 0.5
    info_completeness_score: float = 0.5
    edge_confidence_interval: Optional[EdgeConfidenceInterval] = None


# ── Chief Analyst Agent Models ───────────────────────────────────────────────

class ChiefAnalystAgentOutput(AgentOutputBase):
    """Output from the Chief Analyst agent."""
    agent_name: str = "ChiefAnalystAgent"
    final_report: Optional["FinalReport"] = None


# ── Final Report Models ──────────────────────────────────────────────────────

class MatchOverview(BaseModel):
    home_team: str
    away_team: str
    league: str
    kickoff: str
    competition_level: str
    venue: Optional[str] = None
    weather_forecast: Optional[str] = None


class MarketOddsAnalysis(BaseModel):
    best_odds: dict = Field(default_factory=dict)
    market_consensus: str = ""
    odds_movement_summary: str = ""
    sharp_money_indication: Optional[str] = None
    trap_risk: Optional[str] = None


class QuantitativeProjection(BaseModel):
    ensemble_home_prob: float
    ensemble_draw_prob: float
    ensemble_away_prob: float
    expected_goals_total: Optional[float] = None
    most_likely_score: Optional[str] = None
    value_bets_identified: list[str] = Field(default_factory=list)
    model_std_dev: Optional[float] = None


class TacticalMatchup(BaseModel):
    advantage: Optional[str] = None
    key_battle: Optional[str] = None
    predicted_tempo: Optional[str] = None
    goal_impact: Optional[str] = None


class TeamNews(BaseModel):
    critical_absences: list[str] = Field(default_factory=list)
    fatigue_assessment: Optional[str] = None
    motivation_score: Optional[str] = None
    rotation_risk: Optional[str] = None


class MarketSentiment(BaseModel):
    public_bias: Optional[str] = None
    contrarian_signal: bool = False
    overheating_warning: Optional[str] = None


class HistoricalAnalysis(BaseModel):
    h2h_summary: Optional[str] = None
    similar_odds_pattern: Optional[str] = None
    referee_impact: Optional[str] = None


class RiskAssessment(BaseModel):
    overall_risk: str = "MEDIUM"
    volatility: Optional[str] = None
    model_conflicts: list[str] = Field(default_factory=list)
    betting_recommendation: str = "NO_BET"
    stake_suggestion: Optional[str] = None
    no_bet_reason: Optional[str] = None


class BetRecommendation(BaseModel):
    market: str
    selection: str
    odds: float
    stake_percent: float
    rationale: str
    expected_value: Optional[float] = None
    alternative_market: Optional[str] = None


class FinalVerdict(BaseModel):
    action: FinalAction = FinalAction.NO_BET
    summary: str
    primary_recommendation: Optional[str] = None
    risk_disclaimer: str = "Past performance does not guarantee future results. Betting involves risk. Only wager what you can afford to lose."


class AgentContributions(BaseModel):
    odds_agent_key: Optional[str] = None
    quant_agent_key: Optional[str] = None
    tactical_agent_key: Optional[str] = None
    news_agent_key: Optional[str] = None
    sentiment_agent_key: Optional[str] = None
    historical_agent_key: Optional[str] = None
    risk_agent_key: Optional[str] = None
    referee_agent_key: Optional[str] = None
    sharp_money_agent_key: Optional[str] = None


class FinalReport(BaseModel):
    report_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    match_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    match_overview: MatchOverview
    market_odds_analysis: MarketOddsAnalysis = Field(default_factory=MarketOddsAnalysis)
    quantitative_projection: QuantitativeProjection
    tactical_matchup: TacticalMatchup = Field(default_factory=TacticalMatchup)
    team_news: TeamNews = Field(default_factory=TeamNews)
    market_sentiment: MarketSentiment = Field(default_factory=MarketSentiment)
    historical_analysis: HistoricalAnalysis = Field(default_factory=HistoricalAnalysis)
    risk_assessment: RiskAssessment = Field(default_factory=RiskAssessment)
    betting_recommendation: list[BetRecommendation] = Field(default_factory=list)
    jingcai_recommendation: list[dict] = Field(default_factory=list)
    confidence_rating: ConfidenceRating = ConfidenceRating.C
    final_verdict: FinalVerdict
    agent_contributions: AgentContributions = Field(default_factory=AgentContributions)


# ── Pipeline Models ──────────────────────────────────────────────────────────

class MatchContext(BaseModel):
    """Input context for a match analysis pipeline run."""
    match_id: str
    home_team: str
    away_team: str
    league: str
    kickoff: str = ""
    competition_level: str = "DOMESTIC_LEAGUE"
    venue: Optional[str] = None
    weather_forecast: Optional[str] = None
    opening_odds: Optional[OpeningOdds] = None
    current_odds: Optional[CurrentOdds] = None


class PipelineResult(BaseModel):
    """Complete result from running the full analysis pipeline."""
    match_id: str
    status: str  # "SUCCESS", "PARTIAL", "FAILED"
    agents_executed: list[str]
    agents_failed: list[str]
    execution_time_seconds: float
    final_report: Optional[FinalReport] = None
    error_log: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
