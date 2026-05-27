# Sportsbook Logic — Football Betting Intelligence System
# How bookmakers think, set lines, and manage risk.

---

## 1. Bookmaker's Primary Objective

A bookmaker is NOT trying to predict match outcomes.

A bookmaker IS trying to:
1. Balance the book to earn risk-free vigorish
2. When unbalanced, position on the side they believe has +EV
3. Manage liability exposure across correlated markets
4. Maximize long-term customer lifetime value (LTV)

---

## 2. Line Setting Process

### Stage 1: Fair Value Estimation
- Proprietary models compute "fair" odds
- Inputs: Elo, xG, player ratings, tactical models, etc.
- Output: Raw fair odds for 1X2, Asian handicap, totals

### Stage 2: Market Positioning
- Initial margin applied (typically 5-8% for major leagues, 8-12% for minors)
- Opening line published

### Stage 3: Market Making
- Monitor incoming bet flow
- Adjust lines based on:
  - Volume imbalances
  - Sharp vs. square money identification
  - Competitor line movement
  - New information (team news, weather)

### Stage 4: Risk Management
- Liability caps per market
- Correlated exposure monitoring
- Live betting: dynamic suspension and re-pricing

---

## 3. Sharp vs. Square Money

### Sharp Money (Smart Money)
- Comes from professional bettors / syndicates
- Typically arrives early (right after open) or late (near close)
- Often maximum-stake bets
- Bookmakers RESPECT this money and move lines accordingly

### Square Money (Public Money)
- Comes from recreational bettors
- Biased toward: favorites, home teams, overs, popular teams
- Typically arrives on match day
- Bookmakers TOLERATE this money — may even encourage it

### Key Insight:
When odds move AGAINST the public betting percentage, sharp money is
likely on the unpopular side. This is a powerful signal.

---

## 4. Bookmaker Traps & Tactics

### The "Public Team" Trap
- Popular team (e.g., Man United, Real Madrid, Barcelona) opens at
  attractive-looking odds
- Public piles in
- Line moves AGAINST the public team despite heavy betting
- Bookmaker is fading the public

### The "Steam" Fake
- Rapid odds drop simulated by bookmaker to create urgency
- "Odds are dropping fast — bet now!"
- No actual sharp volume behind the move

### The "Asian Handicap" Tell
- Asian handicap line moves reveal bookmaker confidence
- If AH line moves from -0.5 to -0.75 while odds stay same →
  bookmaker believes favorite is strong
- If odds drop but AH line stays → may be false signal

### The "Over/Under" Tell
- Total goals line that doesn't move despite weather/news suggesting goals
  → bookmaker is confident in their position
- Line that moves aggressively pre-match → sharp information

---

## 5. Key Numbers in Football Betting

### Most Common Margins of Victory
- 1 goal: ~45-50% of all matches
- 0 goals (draw): ~25-28%
- 2 goals: ~15-18%
- 3+ goals: ~7-10%

### Most Common Total Goals
- 2 goals: ~25%
- 3 goals: ~22%
- 1 goal: ~18%
- 0 goals: ~8%
- 4+ goals: ~27%

### Implication:
Asian handicap lines crossing key numbers (0, 0.5, 1.0, 1.5) are
more significant than lines crossing non-key numbers.

---

## 6. League-Specific Characteristics

Different leagues have different "personalities" that bookmakers model:

- **Premier League**: High intensity, relatively high scoring, significant home advantage
- **Serie A**: Tactical, lower scoring, draw-heavy
- **Bundesliga**: High scoring, strong home crowds, fewer draws
- **La Liga**: Technical, moderate scoring, strong home bias for non-top teams
- **Ligue 1**: Physical, moderate-low scoring
- **Eredivisie**: Very high scoring, weak defense
- **J-League / K-League**: Lower scoring, tactical, significant travel effects

Agents must adjust their base rates per league.

---

## 7. Timing Dynamics

### Opening Line (开盘)
- Most vulnerable to sharp money
- Bookmaker is most uncertain
- Best opportunity for value betting

### Mid-Week Movement
- Often driven by team news
- Volume is lower; moves are more informative

### Match Day (比赛日)
- Highest volume
- Public money dominates
- Odds may become less efficient on popular sides

### Live / In-Play (滚球)
- Bookmaker models re-price continuously
- Speed of information is critical
- Suspension risk during key events

---

## 8. Correlation Awareness

Bookmakers manage cross-market correlation:

- Team to win + Over 2.5 goals → positively correlated
- 0-0 at halftime + Under 2.5 full time → highly correlated
- Home win + Home team over 1.5 goals → positively correlated

When analyzing odds, always check for correlated market consistency.
