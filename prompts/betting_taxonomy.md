# Betting Taxonomy — Football Betting Intelligence System
# Standardized terminology for all betting markets and concepts.

---

## 1. Match Result Markets

### 1X2 (European Handicap / Match Result)
- **1**: Home win
- **X**: Draw
- **2**: Away win

### Asian Handicap (AH)
- **-0.25** (Home -0.25): Home win = full win; Draw = half loss; Away win = full loss
- **-0.50** (Home -0.5): Home win = full win; Draw or Away = full loss
- **-0.75** (Home -0.75): Home win by 2+ = full win; Home win by 1 = half win; else = loss
- **-1.00** (Home -1.0): Home win by 2+ = full win; Home win by 1 = push; else = loss
- **+0.25 / +0.50 / +0.75 / +1.00**: Mirror of above for underdog

### Draw No Bet (DNB)
- Home DNB: Home win = win; Draw = push (stake returned); Away win = loss

### Double Chance
- 1X: Home win or Draw
- 12: Home win or Away win (no draw)
- X2: Draw or Away win

---

## 2. Goal Markets

### Over/Under (O/U)
- **O2.5**: 3+ total goals = win; 0-2 goals = loss
- **O2.25**: 3+ goals = win; 2 goals = half loss; 0-1 goals = loss
- **O2.75**: 4+ goals = win; 3 goals = half win; 0-2 goals = loss

### Both Teams to Score (BTTS)
- **BTTS Yes**: Both teams score at least 1 goal
- **BTTS No**: At least one team fails to score

### Team Goals
- **Home Over 1.5**: Home team scores 2+ goals
- **Away Over 0.5**: Away team scores 1+ goals

### Exact Goals
- **Exact Total Goals**: 0, 1, 2, 3, 4, 5, 6+

---

## 3. Combination Markets

### 1X2 + O/U (common in Asia)
- Home & Over 2.5
- Draw & Under 2.5
- etc.

### Asian Handicap + O/U

---

## 4. Odds Terminology

### European Odds (Decimal)
- 2.00 = even money (50% implied probability)
- Formula: implied_probability = 1 / decimal_odds

### Overround / Vigorish / Juice
- Sum of implied probabilities across 1X2 = bookmaker's overround
- Fair odds = odds adjusted to remove overround
- Example: 1=2.50 (40%), X=3.40 (29.4%), 2=2.80 (35.7%)
  Overround = 105.1%; Fair probabilities = implied / 1.051

### Asian Water Level (水位)
- High water: ≥ 1.00 (Hong Kong odds) / ≥ 2.00 (decimal)
- Medium water: ~0.90–0.99 / ~1.90–1.99
- Low water: ≤ 0.89 / ≤ 1.89

### Steam Move (急跌)
- Rapid odds drop within a short time window (minutes to hours)
- Usually indicates sharp money or significant news

### Reverse Line Movement (RLM)
- Odds move opposite to public betting direction
- Strong indicator of sharp money on the unpopular side

---

## 5. Market Behavior Terms

### Trap Odds (诱盘)
- Odds set to lure public money to the "wrong" side
- Characteristics: attractive odds on popular team, subtle movement against

### Block Odds (阻盘)
- Odds set to discourage betting on a side the bookmaker fears
- Characteristics: unappealing odds despite market demand

### Fake Water Drop (虚假降水)
- Water level drops without corresponding volume
- Bookmaker creating false impression of smart money

### Closing Line Value (CLV)
- Beating the closing line = indicator of long-term profitability
- CLV = (odds_taken - closing_odds) / closing_odds

---

## 6. Value Betting Concepts

### Expected Value (EV)
- EV = (probability * (odds - 1)) - ((1 - probability) * 1)
- Positive EV = theoretical edge

### Kelly Criterion
- f* = (bp - q) / b
- b = decimal odds - 1
- p = estimated true probability
- q = 1 - p
- f* = optimal fraction of bankroll

### Closing Line Value (CLV)
- Primary metric for bet quality assessment
- Consistent CLV positive = long-term profitable process
