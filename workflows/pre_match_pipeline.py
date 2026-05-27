"""
Pre-Match Analysis Pipeline — Football Betting Intelligence System.

Orchestrates the full pre-match analysis workflow:
1. Receives match context (teams, odds, league info)
2. Runs all agents in prescribed order
3. Generates final betting analysis report
4. Saves output to disk
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import (
    MatchContext,
    PipelineResult,
    FinalReport,
    OpeningOdds,
    CurrentOdds,
)
from .orchestration import Orchestrator, _ODDS_API_AVAILABLE, _fetch_odds_from_api


class PreMatchPipeline:
    """
    Full pre-match analysis pipeline.

    Usage:
        pipeline = PreMatchPipeline()
        result = pipeline.analyze(match_context)
        pipeline.save_report(result, output_dir)
    """

    def __init__(
        self,
        prompts_dir: Optional[Path] = None,
        output_dir: Optional[Path] = None,
    ):
        base = Path(__file__).resolve().parent.parent
        self.output_dir = output_dir or (base / "outputs" / "reports")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.orchestrator = Orchestrator(
            prompts_dir=prompts_dir or (base / "prompts"),
            log_dir=base / "outputs" / "logs",
        )

    def analyze(self, match_context: MatchContext) -> PipelineResult:
        """
        Run complete pre-match analysis.

        Args:
            match_context: Full match information including odds data

        Returns:
            PipelineResult containing all agent outputs and final report
        """
        return self.orchestrator.run_pipeline(match_context)

    def save_report(
        self,
        result: PipelineResult,
        output_dir: Optional[Path] = None,
    ) -> Path:
        """
        Save the final report as both JSON and Markdown.

        Returns the path to the Markdown report.
        """
        target_dir = output_dir or self.output_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = f"{result.match_id}_{timestamp}"

        # Save JSON report
        if result.final_report:
            json_path = target_dir / f"{base_name}.json"
            json_path.write_text(
                result.final_report.model_dump_json(indent=2),
                encoding="utf-8",
            )
            print(f"[PreMatchPipeline] JSON report saved to: {json_path}")

        # Save Markdown report
        if result.final_report:
            md_content = self.orchestrator.generate_markdown_report(result.final_report)
            md_path = target_dir / f"{base_name}.md"
            md_path.write_text(md_content, encoding="utf-8")
            print(f"[PreMatchPipeline] Markdown report saved to: {md_path}")
            return md_path

        # Save error log if no report
        error_path = target_dir / f"{base_name}_errors.json"
        error_path.write_text(
            json.dumps(
                {
                    "match_id": result.match_id,
                    "status": result.status,
                    "errors": result.error_log,
                    "warnings": result.warnings,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return error_path

    def print_report_summary(self, result: PipelineResult) -> None:
        """Print a concise summary of the analysis to stdout."""
        print(f"\n{'='*70}")
        print(f"  FOOTBALL BETTING INTELLIGENCE — ANALYSIS SUMMARY")
        print(f"{'='*70}")

        if not result.final_report:
            print(f"  Status: {result.status}")
            print(f"  No final report generated.")
            if result.error_log:
                print(f"  Errors: {', '.join(result.error_log)}")
            print(f"{'='*70}\n")
            return

        r = result.final_report
        mo = r.match_overview

        print(f"  Match:    {mo.home_team} vs {mo.away_team}")
        print(f"  League:   {mo.league}")
        print(f"  Kickoff:  {mo.kickoff}")
        print(f"  {'-'*50}")
        print(f"  Home Win:  {r.quantitative_projection.ensemble_home_prob:.1%}")
        print(f"  Draw:      {r.quantitative_projection.ensemble_draw_prob:.1%}")
        print(f"  Away Win:  {r.quantitative_projection.ensemble_away_prob:.1%}")
        print(f"  {'-'*50}")
        print(f"  Risk:      {r.risk_assessment.overall_risk}")
        print(f"  Confidence: {r.confidence_rating.value}")
        print(f"  Verdict:   {r.final_verdict.action.value}")
        print(f"  {'-'*50}")
        print(f"  Agents:    {len(result.agents_executed)}/{len(result.agents_executed) + len(result.agents_failed)} executed")
        print(f"  Time:      {result.execution_time_seconds:.1f}s")
        print(f"  Status:    {result.status}")
        print(f"{'='*70}")
        if r.final_verdict.summary:
            print(f"  Summary: {r.final_verdict.summary}")
        print(f"{'='*70}\n")


# ── Quick-start helpers ───────────────────────────────────────────────────────


def quick_analysis(
    home_team: str,
    away_team: str,
    league: str = "PREMIER_LEAGUE",
    home_odds: float = 1.85,
    draw_odds: float = 3.60,
    away_odds: float = 4.20,
    kickoff: str = "",
) -> PipelineResult:
    """
    Run a quick analysis with minimal input (uses hardcoded/synthetic odds).

    Args:
        home_team: Home team name
        away_team: Away team name
        league: League identifier
        home_odds: Current home win odds (decimal)
        draw_odds: Current draw odds (decimal)
        away_odds: Current away win odds (decimal)
        kickoff: Match kickoff time string

    Returns:
        PipelineResult with full analysis
    """
    match_id = f"{home_team}_{away_team}".replace(" ", "_").lower()

    ctx = MatchContext(
        match_id=match_id,
        home_team=home_team,
        away_team=away_team,
        league=league,
        kickoff=kickoff,
        opening_odds=OpeningOdds(
            home=home_odds * 1.02,
            draw=draw_odds * 0.98,
            away=away_odds * 1.01,
            over_25=1.90,
            under_25=1.90,
        ),
        current_odds=CurrentOdds(
            home=home_odds,
            draw=draw_odds,
            away=away_odds,
            over_25=1.88,
            under_25=1.92,
        ),
    )

    pipeline = PreMatchPipeline()
    result = pipeline.analyze(ctx)
    pipeline.save_report(result)
    pipeline.print_report_summary(result)

    return result


def quick_analysis_with_api(
    home_team: str,
    away_team: str,
    league: str = "PREMIER_LEAGUE",
    home_odds: float = 1.85,
    draw_odds: float = 3.60,
    away_odds: float = 4.20,
    kickoff: str = "",
) -> PipelineResult:
    """
    Run analysis attempting to fetch live odds from The Odds API first.

    Falls back to hardcoded odds if API is unavailable or key not configured.
    """
    match_id = f"{home_team}_{away_team}".replace(" ", "_").lower()

    # Default odds as fallback
    opening = OpeningOdds(
        home=home_odds * 1.02,
        draw=draw_odds * 0.98,
        away=away_odds * 1.01,
        over_25=1.90,
        under_25=1.90,
    )
    current = CurrentOdds(
        home=home_odds,
        draw=draw_odds,
        away=away_odds,
        over_25=1.88,
        under_25=1.92,
    )

    # Try fetching from API
    api_data = None
    if _ODDS_API_AVAILABLE:
        ctx_temp = MatchContext(
            match_id=match_id,
            home_team=home_team,
            away_team=away_team,
            league=league,
            kickoff=kickoff,
        )
        api_data = _fetch_odds_from_api(home_team, away_team, league, ctx_temp)

    if api_data:
        opening = api_data["opening"]
        current = api_data["current"]
        print(f"[PreMatchPipeline] Using LIVE odds from The Odds API")
        print(f"  {home_team}: {current.home} | Draw: {current.draw} | {away_team}: {current.away}")
    else:
        print(f"[PreMatchPipeline] API unavailable — using hardcoded/synthetic odds")
        print(f"  To use live odds, get a free API key at https://odds-api.io")
        print(f"  and set ODDS_API_KEY env var or create config/odds_api_key.txt")

    ctx = MatchContext(
        match_id=match_id,
        home_team=home_team,
        away_team=away_team,
        league=league,
        kickoff=kickoff,
        opening_odds=opening,
        current_odds=current,
    )

    pipeline = PreMatchPipeline()
    result = pipeline.analyze(ctx)
    pipeline.save_report(result)
    pipeline.print_report_summary(result)

    return result
