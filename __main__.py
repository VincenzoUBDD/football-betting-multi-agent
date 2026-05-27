"""
Football Betting Intelligence System — Main Entry Point.

Usage:
    python -m football_betting_intel --home "Man City" --away "Liverpool" --league "PREMIER_LEAGUE"
    python -m football_betting_intel --demo
"""

import argparse
import sys
from pathlib import Path

# Ensure the package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from workflows.pre_match_pipeline import PreMatchPipeline, quick_analysis, quick_analysis_with_api
from workflows.models import MatchContext, OpeningOdds, CurrentOdds
from storage.calibration import (
    enter_result,
    add_result_entry,
    print_calibration_report,
    compute_metrics,
)


def run_demo():
    """Run a comprehensive demonstration of the system."""
    print("=" * 70)
    print("  FOOTBALL BETTING INTELLIGENCE MULTI-AGENT SYSTEM")
    print("  Professional Sportsbook Analyst Architecture")
    print("=" * 70)
    print()

    # Demo 1: Premier League match
    print("DEMO 1: Premier League — Arsenal vs Chelsea")
    print("-" * 50)
    result1 = quick_analysis(
        home_team="Arsenal",
        away_team="Chelsea",
        league="PREMIER_LEAGUE",
        home_odds=1.90,
        draw_odds=3.50,
        away_odds=4.00,
        kickoff="2026-05-28 15:00 GMT",
    )

    print()
    print("DEMO 2: Serie A — AC Milan vs Inter Milan (Derby)")
    print("-" * 50)
    result2 = quick_analysis(
        home_team="AC Milan",
        away_team="Inter Milan",
        league="SERIE_A",
        home_odds=2.80,
        draw_odds=3.20,
        away_odds=2.50,
        kickoff="2026-05-28 20:45 CET",
    )

    print()
    print("DEMO 3: Bundesliga — Bayern Munich vs Borussia Dortmund")
    print("-" * 50)
    result3 = quick_analysis(
        home_team="Bayern Munich",
        away_team="Borussia Dortmund",
        league="BUNDESLIGA",
        home_odds=1.55,
        draw_odds=4.50,
        away_odds=5.50,
        kickoff="2026-05-29 18:30 CET",
    )

    print()
    print("=" * 70)
    print("  ALL DEMOS COMPLETE")
    print(f"  Reports saved to: outputs/reports/")
    print("=" * 70)


def run_single_match(args):
    """Run analysis for a single match specified via CLI args."""
    if args.use_api:
        result = quick_analysis_with_api(
            home_team=args.home,
            away_team=args.away,
            league=args.league,
            home_odds=args.home_odds or 1.85,
            draw_odds=args.draw_odds or 3.50,
            away_odds=args.away_odds or 3.80,
            kickoff=args.kickoff or "",
        )
        return

    ctx = MatchContext(
        match_id=f"{args.home}_{args.away}".replace(" ", "_").lower(),
        home_team=args.home,
        away_team=args.away,
        league=args.league,
        kickoff=args.kickoff or "",
        opening_odds=OpeningOdds(
            home=args.home_odds * 1.02 if args.home_odds else 1.90,
            draw=args.draw_odds * 0.98 if args.draw_odds else 3.50,
            away=args.away_odds * 1.01 if args.away_odds else 3.80,
            over_25=args.over_odds or 1.90,
            under_25=args.under_odds or 1.90,
        ),
        current_odds=CurrentOdds(
            home=args.home_odds or 1.85,
            draw=args.draw_odds or 3.50,
            away=args.away_odds or 3.80,
            over_25=args.over_odds or 1.88,
            under_25=args.under_odds or 1.92,
        ),
    )

    pipeline = PreMatchPipeline()
    result = pipeline.analyze(ctx)
    pipeline.save_report(result)
    pipeline.print_report_summary(result)


def main():
    parser = argparse.ArgumentParser(
        description="Football Betting Intelligence Multi-Agent System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m football_betting_intel --demo
  python -m football_betting_intel --home "Man City" --away "Liverpool" --league PREMIER_LEAGUE
  python -m football_betting_intel --home "Real Madrid" --away "Barcelona" --league LA_LIGA --home_odds 2.10 --draw_odds 3.40 --away_odds 3.30
        """,
    )

    parser.add_argument("--demo", action="store_true", help="Run demonstration with sample matches")
    parser.add_argument("--home", type=str, help="Home team name")
    parser.add_argument("--away", type=str, help="Away team name")
    parser.add_argument("--league", type=str, default="PREMIER_LEAGUE",
                        help="League identifier (PREMIER_LEAGUE, SERIE_A, BUNDESLIGA, LA_LIGA, LIGUE_1)")
    parser.add_argument("--kickoff", type=str, help="Kickoff time (e.g., '2026-05-28 15:00 GMT')")
    parser.add_argument("--home_odds", type=float, help="Current home win decimal odds")
    parser.add_argument("--draw_odds", type=float, help="Current draw decimal odds")
    parser.add_argument("--away_odds", type=float, help="Current away win decimal odds")
    parser.add_argument("--over_odds", type=float, help="Current over 2.5 decimal odds")
    parser.add_argument("--under_odds", type=float, help="Current under 2.5 decimal odds")
    parser.add_argument("--use-api", action="store_true",
                        help="Attempt to fetch live odds from The Odds API (requires API key)")
    parser.add_argument("--calibrate", action="store_true",
                        help="Print calibration report (prediction vs actual results)")
    parser.add_argument("--enter-result", type=str, metavar="MATCH_ID",
                        help="Enter match result (use with --home_score, --away_score)")
    parser.add_argument("--home_score", type=int, help="Actual home goals (for --enter-result)")
    parser.add_argument("--away_score", type=int, help="Actual away goals (for --enter-result)")

    args = parser.parse_args()

    if args.demo:
        run_demo()
    elif args.calibrate:
        print_calibration_report()
    elif args.enter_result:
        if args.home_score is None or args.away_score is None:
            print("Error: --home_score and --away_score required with --enter-result")
            sys.exit(1)
        enter_result(args.enter_result, args.home_score, args.away_score)
    elif args.home and args.away:
        run_single_match(args)
    else:
        parser.print_help()
        print("\nRun with --demo for demonstration or specify --home and --away for match analysis.")


if __name__ == "__main__":
    main()
