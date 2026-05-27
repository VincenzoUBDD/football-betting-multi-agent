# Football Betting Intelligence Multi-Agent System

10-agent collaborative football betting analysis platform. Generates full match reports
with both international market recommendations and China Sports Lottery (竞彩) adaptations.

## Quick Start

```bash
# Analyze a match
python __main__.py --home "Man City" --away "Liverpool" --league PREMIER_LEAGUE \
  --home_odds 1.85 --draw_odds 3.60 --away_odds 4.20

# Run 3-match demo
python __main__.py --demo

# Enter match result after the game
python __main__.py --enter-result crystal_palace_rayo_vallecano --home_score 2 --away_score 1

# View calibration report (prediction vs reality)
python __main__.py --calibrate
```

## Architecture

```
Match Context (teams, odds, league)
        │
        ├──→ News Agent       (injuries, fatigue, motivation)
        ├──→ Odds Agent       (market odds, trap detection, sharp side)
        ├──→ Quant Agent      (Poisson, Elo, Monte Carlo ensemble)
        ├──→ Tactical Agent   (formation, pressing, set pieces)
        ├──→ Historical Agent (H2H, similar-odds patterns, referee history)
        ├──→ Sentiment Agent  (public bias, contrarian signals)
        ├──→ Referee Agent    (card/penalty tendencies, home bias)
        ├──→ Sharp Money Agent(steam moves, RLM, exchange analysis)
        │
        └──→ Risk Agent ──→ Chief Analyst ──→ Final Report (JSON + Markdown)
                                                  │
                                                  ├── International recommendations
                                                  └── 竞彩 recommendations (auto-mapped)
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `--home / --away / --league` | Analyze a single match |
| `--home_odds / --draw_odds / --away_odds` | Set current odds |
| `--demo` | Run 3-match demo |
| `--calibrate` | Print calibration report |
| `--enter-result <match_id> --home_score X --away_score Y` | Enter match result |
| `--use-api` | Fetch live odds from API |

## 竞彩 (China Sports Lottery) Support

The Chief Analyst automatically maps model outputs to 竞彩's limited market set:

| 竞彩玩法 | Mapping Logic |
|----------|--------------|
| 胜平负 (1X2) | Direct model probability |
| 让球胜平负 (-1/+1) | Handicap-adjusted probabilities, avoids contradictory picks |
| 总进球数 (0-7+) | Exact score probabilities aggregated into goal buckets |
| 比分 | Top 3 most likely exact scores |

Markets NOT available in 竞彩 (auto-excluded): Under/Over X.5, BTTS, Asian handicap non-integer, Double Chance.

## Calibration System

Prediction reports are saved to `outputs/reports/`. After matches finish, enter results
to build a feedback loop that corrects model biases.

### Workflow

```
1. Run analysis  →  JSON report saved to outputs/reports/
2. Match finishes →  python __main__.py --enter-result <match_id> --home_score X --away_score Y
3. View stats     →  python __main__.py --calibrate
4. When league has ≥3 results → correction factors become available
```

### Key Metrics

| Metric | Description |
|--------|-------------|
| Brier Score | Probability accuracy (0=perfect, 0.33=random) |
| Home/Draw/Away Bias | Systematic over/under-estimation per outcome |
| Goals Bias | Total goals prediction error |
| Directional Accuracy | % of matches where highest-probability outcome was correct |
| ROI | Return on recommended stakes |

### Applying Calibration

```python
from storage.calibration import apply_calibration, get_correction_factors

# Get correction factors (returns None if < 3 samples for this league)
factors = get_correction_factors("COPA_LIBERTADORES")
# → {"home_adjust": -0.032, "draw_adjust": +0.018, "away_adjust": +0.014, ...}

# Apply to raw model probabilities
adj_h, adj_d, adj_a = apply_calibration(0.63, 0.22, 0.15, "COPA_LIBERTADORES")
```

## Project Structure

```
football_betting_intel/
├── agents/                    # Agent system prompt definitions (*.md)
├── schemas/                   # JSON Schema definitions
├── prompts/                   # Shared rules and guidelines
├── workflows/                 # Core Python implementation
│   ├── models.py              # Pydantic data models
│   ├── compute_engine.py      # Math engine (Poisson, Elo, MC, Kelly)
│   ├── orchestration.py       # Agent execution + 竞彩 mapping + report generation
│   ├── pre_match_pipeline.py  # Pre-match analysis pipeline
│   ├── live_match_pipeline.py # Live/in-play pipeline skeleton
│   └── odds_api_client.py     # Odds API integration
├── storage/                   # Calibration & persistence
│   └── calibration.py         # Prediction-vs-reality matching, bias computation
├── outputs/                   # Generated reports and results
│   ├── reports/               # JSON + Markdown reports per match
│   └── results.json           # Match results waiting for scores
├── __main__.py                # CLI entry point
└── README.md
```

## Mathematical Models

- **Poisson Goal Model**: Bivariate Poisson for score distribution
- **Elo Rating System**: With home advantage and draw adjustment
- **Monte Carlo Simulation**: 10,000+ iterations
- **Bayesian Updating**: Prior x likelihood ratio -> posterior
- **Kelly Criterion**: Optimal stake sizing with fractional Kelly
- **Ensemble Aggregation**: Weighted model blending

## Confidence Ratings

| Rating | Description |
|--------|-------------|
| S | Elite — multi-model consensus + clear mispricing |
| A+ | Very high — core logic highly consistent |
| A | High — strong signal, minor uncertainty |
| B+ | Above average — clear edge, moderate uncertainty |
| B | Average — some edge, conflicting signals |
| C | Weak — market efficient, marginal edge |
| D | Avoid — NO BET zone |
