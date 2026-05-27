"""
Odds API Client — Football Betting Intelligence System.

Integrates with The Odds API (odds-api.io) for real-time betting odds.
Supports 250+ bookmakers, odds movement tracking, and value bet detection.

API Key: Obtain free key at https://odds-api.io
Free tier: 5,000 req/hr, 2 bookmakers per request, all endpoints.
"""

from __future__ import annotations

import os
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from odds_api import OddsAPIClient, AsyncOddsAPIClient
from odds_api.exceptions import OddsAPIError, InvalidAPIKeyError, RateLimitExceededError

logger = logging.getLogger("FootballBettingIntel.OddsAPI")

# ── Configuration ────────────────────────────────────────────────────────────

# Pinnacle = sharpest book; Bet365 = highest volume
DEFAULT_BOOKMAKERS = "pinnacle,bet365"

# Football/Soccer sport keys in the API
SOCCER_SPORT_KEYS = [
    "soccer", "soccer_epl", "soccer_england_efl_cup",
    "soccer_spain_la_liga", "soccer_germany_bundesliga",
    "soccer_italy_serie_a", "soccer_france_ligue_one",
    "soccer_uefa_champs_league", "soccer_uefa_europa_league",
    "soccer_uefa_europa_conference_league",
    "soccer_netherlands_eredivisie",
]

# Market mapping: API name → our system name
MARKET_MAP = {
    "h2h": "1X2",
    "totals": "OVER_UNDER",
    "btts": "BTTS",
    "spreads": "ASIAN_HANDICAP",
    "both_teams_to_score": "BTTS",
}


class OddsAPIClientWrapper:
    """
    Wrapper around The Odds API SDK for football betting analysis.

    Usage:
        client = OddsAPIClientWrapper(api_key="your_key")
        # or set ODDS_API_KEY env var
        client = OddsAPIClientWrapper()

        # Find a match
        event = client.find_match("Arsenal", "Chelsea")

        # Get full odds analysis
        analysis = client.get_match_odds_analysis(event["event_id"])
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        bookmakers: str = DEFAULT_BOOKMAKERS,
        config_path: Optional[Path] = None,
    ):
        """
        Initialize the Odds API client.

        API key resolution order:
        1. api_key parameter
        2. ODDS_API_KEY environment variable
        3. Config file at config_path or project_root/config/odds_api_key.txt
        """
        self.api_key = self._resolve_api_key(api_key, config_path)
        if not self.api_key:
            raise InvalidAPIKeyError(
                "No API key found. Get a free key at https://odds-api.io "
                "and set ODDS_API_KEY env var or pass api_key parameter."
            )

        self.bookmakers = bookmakers
        self.client = OddsAPIClient(api_key=self.api_key, timeout=15)
        self._selected_bookmakers: Optional[list[str]] = None
        self._bookmaker_info: dict[str, dict] = {}

        logger.info(f"OddsAPIClient initialized with bookmakers: {bookmakers}")

    def _resolve_api_key(
        self, api_key: Optional[str], config_path: Optional[Path]
    ) -> Optional[str]:
        """Resolve API key from multiple sources."""
        if api_key:
            return api_key

        env_key = os.environ.get("ODDS_API_KEY")
        if env_key:
            return env_key

        # Try config file
        if config_path and config_path.exists():
            return config_path.read_text(encoding="utf-8").strip()

        # Try default config location
        default_config = (
            Path(__file__).resolve().parent.parent / "config" / "odds_api_key.txt"
        )
        if default_config.exists():
            return default_config.read_text(encoding="utf-8").strip()

        return None

    # ── Bookmaker Management ──────────────────────────────────────────────

    def select_bookmakers(self, bookmakers: str) -> list[str]:
        """Select which bookmakers to query. Free tier: max 2."""
        result = self.client.select_bookmakers(bookmakers)
        self._selected_bookmakers = bookmakers.split(",")
        logger.info(f"Selected bookmakers: {bookmakers}")
        return result

    def get_available_bookmakers(self) -> list[dict]:
        """Get list of all available bookmakers."""
        bookmakers = self.client.get_bookmakers()
        self._bookmaker_info = {b["key"]: b for b in bookmakers}
        return bookmakers

    # ── Match Discovery ───────────────────────────────────────────────────

    def find_match(
        self,
        home_team: str,
        away_team: str,
        sport: str = "soccer",
        league: Optional[str] = None,
    ) -> Optional[dict]:
        """
        Find a specific match by team names.

        Args:
            home_team: Home team name (fuzzy match)
            away_team: Away team name (fuzzy match)
            sport: Sport key (default: soccer)
            league: Optional league filter

        Returns:
            Event dict or None if not found
        """
        # Try exact event ID search first (if numeric)
        # Then search by name
        events = self.client.search_events(f"{home_team} vs {away_team}")

        if events:
            for event in events:
                if (
                    home_team.lower() in event.get("home_team", "").lower()
                    and away_team.lower() in event.get("away_team", "").lower()
                ):
                    return event

        # Try getting all events and filtering
        try:
            all_events = self.client.get_events(sport=sport, league=league)
            for event in all_events:
                home = event.get("home_team", "")
                away = event.get("away_team", "")
                if home_team.lower() in home.lower() and away_team.lower() in away.lower():
                    return event
        except Exception:
            pass

        return None

    def get_upcoming_matches(
        self,
        sport: str = "soccer",
        league: Optional[str] = None,
        limit: int = 20,
    ) -> list[dict]:
        """Get upcoming matches for a sport/league."""
        events = self.client.get_events(sport=sport, league=league)
        if limit and len(events) > limit:
            events = events[:limit]
        return events

    def get_live_matches(self, sport: str = "soccer") -> list[dict]:
        """Get currently live matches."""
        try:
            return self.client.get_live_events(sport=sport)
        except Exception:
            return []

    # ── Odds Data ─────────────────────────────────────────────────────────

    def get_odds(
        self,
        event_id: str,
        markets: str = "h2h,totals,btts,spreads",
    ) -> dict:
        """
        Get current odds for a specific event.

        Args:
            event_id: Event ID from get_events or find_match
            markets: Comma-separated market list

        Returns:
            Odds data dict with bookmaker breakdown
        """
        events = self.client.get_odds_for_multiple_events(
            event_ids=event_id,
            bookmakers=self.bookmakers,
        )
        if events:
            # The API returns a list; filter for our event
            for event in events:
                if str(event.get("event_id", "")) == str(event_id):
                    return event
            # If event_id not matched, return first result
            return events[0] if events else {}

        # Fallback: try single event odds
        try:
            return self.client.get_event_by_id(int(event_id))
        except Exception:
            return {}

    def get_odds_movement(
        self,
        event_id: str,
        market: str = "h2h",
    ) -> list[dict]:
        """
        Track odds movement history for an event.

        This shows how odds changed from open to current,
        which is critical for sharp money detection.
        """
        movements = []
        for bookmaker in self.bookmakers.split(","):
            try:
                result = self.client.get_odds_movement(
                    event_id=event_id,
                    bookmaker=bookmaker.strip(),
                    market=market,
                )
                movements.extend(result)
            except Exception:
                continue
        return movements

    # ── Value Bet Detection ───────────────────────────────────────────────

    def get_value_bets(
        self,
        include_details: bool = True,
    ) -> list[dict]:
        """
        Get pre-computed value bets (positive EV opportunities).

        The API itself identifies where model probability
        exceeds market-implied probability.
        """
        value_bets = []
        for bookmaker in self.bookmakers.split(","):
            try:
                bets = self.client.get_value_bets(
                    bookmaker=bookmaker.strip(),
                    include_event_details=include_details,
                )
                value_bets.extend(bets)
            except Exception:
                continue
        return value_bets

    # ── Match Analysis (Integrated) ───────────────────────────────────────

    def get_match_odds_analysis(self, event_id: str) -> dict:
        """
        Get comprehensive odds analysis for a match.

        Returns a dict ready to feed into our Odds Agent.
        """
        odds_data = self.get_odds(event_id)

        if not odds_data:
            return {"error": "No odds data available", "event_id": event_id}

        # Extract bookmaker-specific odds
        bookmakers_data = odds_data.get("bookmakers", [])

        # Parse 1X2 market
        h2h_odds = self._extract_h2h(bookmakers_data)

        # Parse totals market
        totals = self._extract_totals(bookmakers_data)

        # Parse spreads (Asian handicap)
        spreads = self._extract_spreads(bookmakers_data)

        # Get best odds
        best_odds = self._get_best_odds(h2h_odds)

        # Compute market consensus
        avg_odds = self._get_average_odds(h2h_odds)

        # Detect sharp vs public side
        sharp_side = self._detect_sharp_side(h2h_odds, odds_data)

        # Try to get opening odds from movement data
        opening_odds = self._estimate_opening_odds(event_id)

        return {
            "event_id": event_id,
            "home_team": odds_data.get("home_team", ""),
            "away_team": odds_data.get("away_team", ""),
            "commence_time": odds_data.get("commence_time", ""),
            "sport": odds_data.get("sport_key", ""),
            "bookmakers_count": len(bookmakers_data),
            "bookmakers_queried": self.bookmakers,
            # Odds data
            "best_odds": best_odds,
            "average_odds": avg_odds,
            "opening_odds": opening_odds,
            "current_odds": best_odds,  # Best current = what we use
            "h2h_by_bookmaker": h2h_odds,
            "totals_by_bookmaker": totals,
            "spreads_by_bookmaker": spreads,
            # Analysis
            "sharp_side": sharp_side["side"],
            "sharp_confidence": sharp_side["confidence"],
            "market_consensus": self._market_consensus(avg_odds),
            "odds_movement_detected": self._check_movement(opening_odds, best_odds),
        }

    # ── Internal Parsing Methods ──────────────────────────────────────────

    def _extract_h2h(self, bookmakers_data: list) -> dict:
        """Extract 1X2 odds from bookmaker data."""
        result = {}
        for book in bookmakers_data:
            key = book.get("key", "unknown")
            markets = book.get("markets", [])
            for market in markets:
                if market.get("key") == "h2h":
                    outcomes = market.get("outcomes", [])
                    result[key] = {
                        "home": next(
                            (o["price"] for o in outcomes if o["name"] == outcomes[0]["name"]),
                            None,
                        ),
                        "away": next(
                            (o["price"] for o in outcomes if o["name"] == outcomes[-1]["name"]),
                            None,
                        ),
                        "draw": next(
                            (o["price"] for o in outcomes if o["name"].lower() == "draw"),
                            None,
                        ),
                        "last_update": market.get("last_update", ""),
                    }
                    break  # Only process first h2h market per bookmaker
        return result

    def _extract_totals(self, bookmakers_data: list) -> dict:
        """Extract Over/Under totals odds."""
        result = {}
        for book in bookmakers_data:
            key = book.get("key", "unknown")
            markets = book.get("markets", [])
            for market in markets:
                if market.get("key") == "totals":
                    outcomes = market.get("outcomes", [])
                    over_outcomes = [o for o in outcomes if o["name"] == "Over"]
                    under_outcomes = [o for o in outcomes if o["name"] == "Under"]
                    if over_outcomes and under_outcomes:
                        result[key] = {
                            "line": over_outcomes[0].get("point", 2.5),
                            "over": over_outcomes[0].get("price"),
                            "under": under_outcomes[0].get("price"),
                        }
                    break
        return result

    def _extract_spreads(self, bookmakers_data: list) -> dict:
        """Extract Asian Handicap / spreads data."""
        result = {}
        for book in bookmakers_data:
            key = book.get("key", "unknown")
            markets = book.get("markets", [])
            for market in markets:
                if market.get("key") == "spreads":
                    outcomes = market.get("outcomes", [])
                    if len(outcomes) >= 2:
                        result[key] = {
                            "home_line": outcomes[0].get("point"),
                            "home_price": outcomes[0].get("price"),
                            "away_line": outcomes[1].get("point"),
                            "away_price": outcomes[1].get("price"),
                        }
                    break
        return result

    def _get_best_odds(self, h2h_odds: dict) -> dict:
        """Get the best (highest) odds for each outcome across bookmakers."""
        if not h2h_odds:
            return {"home": 0, "draw": 0, "away": 0}

        return {
            "home": max(
                (b["home"] for b in h2h_odds.values() if b.get("home")),
                default=0,
            ),
            "draw": max(
                (b["draw"] for b in h2h_odds.values() if b.get("draw")),
                default=0,
            ),
            "away": max(
                (b["away"] for b in h2h_odds.values() if b.get("away")),
                default=0,
            ),
        }

    def _get_average_odds(self, h2h_odds: dict) -> dict:
        """Compute average odds across bookmakers."""
        if not h2h_odds:
            return {"home": 0, "draw": 0, "away": 0}

        homes = [b["home"] for b in h2h_odds.values() if b.get("home")]
        draws = [b["draw"] for b in h2h_odds.values() if b.get("draw")]
        aways = [b["away"] for b in h2h_odds.values() if b.get("away")]

        return {
            "home": round(sum(homes) / len(homes), 2) if homes else 0,
            "draw": round(sum(draws) / len(draws), 2) if draws else 0,
            "away": round(sum(aways) / len(aways), 2) if aways else 0,
        }

    def _detect_sharp_side(self, h2h_odds: dict, odds_data: dict) -> dict:
        """
        Detect sharp money side by comparing bookmaker odds.

        Heuristic: Pinnacle odds that differ significantly from
        other bookmakers suggest sharp money direction.
        """
        if len(h2h_odds) < 2:
            return {"side": "NONE_DETECTED", "confidence": 0.0}

        # Get Pinnacle odds if available (sharpest book)
        pinnacle = h2h_odds.get("pinnacle", {})
        if not pinnacle:
            return {"side": "NONE_DETECTED", "confidence": 0.0}

        # Compare to other bookmakers
        deviations = {"home": 0.0, "draw": 0.0, "away": 0.0}
        count = 0
        for key, odds in h2h_odds.items():
            if key == "pinnacle":
                continue
            for outcome in ["home", "draw", "away"]:
                if pinnacle.get(outcome) and odds.get(outcome):
                    deviations[outcome] += pinnacle[outcome] - odds[outcome]
            count += 1

        if count == 0:
            return {"side": "NONE_DETECTED", "confidence": 0.0}

        # Average deviation
        avg_dev = {k: v / count for k, v in deviations.items()}

        # If Pinnacle offers lower odds on side X (cheaper = sharper money on X)
        # Pinnacle odds lower → sharp money is on this outcome
        min_dev = min(avg_dev.values())
        max_dev = max(avg_dev.values())

        spread = max_dev - min_dev
        if spread < 0.03:
            return {"side": "NONE_DETECTED", "confidence": 0.0}

        # Sharp side = where Pinnacle odds are lower
        sharp_outcome = min(avg_dev, key=avg_dev.get)
        side_map = {"home": "HOME", "draw": "DRAW", "away": "AWAY"}
        confidence = min(spread * 10, 1.0)

        return {"side": side_map.get(sharp_outcome, "NONE_DETECTED"), "confidence": round(confidence, 2)}

    def _market_consensus(self, avg_odds: dict) -> str:
        """Determine market consensus direction."""
        if not avg_odds or not avg_odds.get("home"):
            return "NEUTRAL"

        home = 1 / avg_odds["home"] if avg_odds["home"] > 0 else 0
        draw = 1 / avg_odds["draw"] if avg_odds.get("draw", 0) > 0 else 0
        away = 1 / avg_odds["away"] if avg_odds.get("away", 0) > 0 else 0

        total = home + draw + away
        if total == 0:
            return "NEUTRAL"

        home_pct = home / total
        away_pct = away / total

        if home_pct > away_pct + 0.08:
            return "HOME"
        elif away_pct > home_pct + 0.08:
            return "AWAY"
        return "NEUTRAL"

    def _estimate_opening_odds(self, event_id: str) -> dict:
        """Estimate opening odds from movement data."""
        try:
            movements = self.get_odds_movement(event_id, market="h2h")
            if not movements:
                return {}

            # First data point ≈ opening odds
            earliest = movements[0] if movements else {}
            return {
                "home": earliest.get("home_odds", 0),
                "draw": earliest.get("draw_odds", 0),
                "away": earliest.get("away_odds", 0),
            }
        except Exception:
            return {}

    def _check_movement(self, opening: dict, current: dict) -> dict:
        """Check if significant odds movement has occurred."""
        if not opening or not current:
            return {"detected": False}

        movements = {}
        for key in ["home", "draw", "away"]:
            if opening.get(key) and current.get(key) and opening[key] > 0:
                change_pct = (current[key] - opening[key]) / opening[key] * 100
                direction = (
                    "shortening" if change_pct < -1
                    else "lengthening" if change_pct > 1
                    else "stable"
                )
                movements[key] = {
                    "change_pct": round(change_pct, 2),
                    "direction": direction,
                }

        return {
            "detected": any(
                abs(m["change_pct"]) > 1 for m in movements.values()
            ),
            "movements": movements,
        }


# ── Async Client ─────────────────────────────────────────────────────────────


class AsyncOddsAPIClientWrapper:
    """Async version for high-throughput analysis."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        bookmakers: str = DEFAULT_BOOKMAKERS,
    ):
        self.api_key = api_key or os.environ.get("ODDS_API_KEY", "")
        if not self.api_key:
            raise InvalidAPIKeyError(
                "No API key found. Get a free key at https://odds-api.io"
            )
        self.bookmakers = bookmakers
        self.client = AsyncOddsAPIClient(api_key=self.api_key, timeout=15)

    async def get_odds_async(self, event_id: str) -> dict:
        """Async odds retrieval."""
        return await self.client.get_event_by_id(int(event_id))

    async def close(self):
        """Close the async client session."""
        await self.client.close()


# ── CLI Test ─────────────────────────────────────────────────────────────────


def test_connection(api_key: Optional[str] = None):
    """Test the Odds API connection and print summary."""
    print("=" * 60)
    print("  ODDS API CONNECTION TEST")
    print("=" * 60)

    try:
        client = OddsAPIClientWrapper(api_key=api_key)
    except InvalidAPIKeyError as e:
        print(f"  ERROR: {e}")
        print()
        print("  To get a free API key:")
        print("  1. Visit https://odds-api.io")
        print("  2. Sign up (no credit card required)")
        print("  3. Copy your API key")
        print("  4. Set env var: set ODDS_API_KEY=your_key")
        print("     or create file: config/odds_api_key.txt")
        return

    # Test sports
    print()
    print("[1] Testing sports endpoint...")
    try:
        sports = client.client.get_sports()
        soccer_sports = [s for s in sports if "soccer" in s.get("key", "")]
        print(f"     Found {len(soccer_sports)} soccer leagues:")
        for s in soccer_sports[:10]:
            print(f"       - {s.get('key')}: {s.get('description', '')}")
    except Exception as e:
        print(f"     ERROR: {e}")

    # Test events
    print()
    print("[2] Testing events (soccer_epl)...")
    try:
        events = client.client.get_events(sport="soccer_epl")
        print(f"     Found {len(events)} events")
        for e in events[:3]:
            print(f"       - {e.get('home_team')} vs {e.get('away_team')} | {e.get('commence_time')}")
    except Exception as e:
        print(f"     ERROR: {e}")

    # Test bookmakers
    print()
    print("[3] Testing bookmakers...")
    try:
        bookmakers = client.get_available_bookmakers()
        print(f"     {len(bookmakers)} bookmakers available")
        for b in bookmakers[:5]:
            print(f"       - {b.get('key')}: {b.get('title', '')}")
    except Exception as e:
        print(f"     ERROR: {e}")

    # Test value bets
    print()
    print("[4] Testing value bets...")
    try:
        bets = client.get_value_bets(include_details=False)
        print(f"     Found {len(bets)} value bet opportunities")
        for b in bets[:3]:
            print(f"       - {b.get('event', {}).get('home_team', '?')} vs {b.get('event', {}).get('away_team', '?')}")
    except Exception as e:
        print(f"     ERROR: {e}")

    print()
    print("=" * 60)
    print("  CONNECTION TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    test_connection()
