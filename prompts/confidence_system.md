# Confidence Rating System — Football Betting Intelligence System

---

## Rating Scale

| Rating | Label    | Definition |
|--------|----------|------------|
| S      | Elite    | Multi-model strong consensus + clear market mispricing + high data quality + low uncertainty |
| A+     | Very High| Core logic highly consistent across agents; one minor uncertainty remains |
| A      | High     | Strong signal but moderate uncertainty on one dimension |
| B+     | Above Avg| Clear edge detected but meaningful uncertainty on 1-2 factors |
| B      | Average  | Some edge suggested; conflicting signals present |
| C      | Weak     | Market appears efficient; marginal or no edge detected |
| D      | Avoid    | High uncertainty, conflicting data, or extreme risk — NO BET zone |

---

## Confidence Calculation Framework

Confidence is NOT a single number. It is a multi-dimensional assessment:

### Dimension 1: Model Consensus (weight: 30%)
- How well do Poisson, xG, Elo, and Monte Carlo models agree?
- Range of probability estimates across models
- Standard deviation of model outputs

### Dimension 2: Market Signal Clarity (weight: 25%)
- Is the odds movement direction clear?
- Is sharp money identifiable?
- Is there a consistent signal across bookmakers?

### Dimension 3: Data Quality (weight: 20%)
- Sample size adequacy
- Recency of data
- Reliability of sources
- Completeness of fundamental data

### Dimension 4: Tactical/Structural Clarity (weight: 15%)
- Is the tactical matchup well-defined?
- Are key player absences known?
- Is the motivational picture clear?

### Dimension 5: Contradiction Count (weight: 10%)
- Number of unresolved contradictions
- Severity of contradictions
- Impact on core hypothesis

---

## Confidence Scoring Algorithm

```python
def compute_confidence(
    model_consensus: float,      # 0.0–1.0
    market_clarity: float,       # 0.0–1.0
    data_quality: float,         # 0.0–1.0
    tactical_clarity: float,     # 0.0–1.0
    contradiction_penalty: float # 0.0–1.0 (higher = more contradictions)
) -> str:

    raw_score = (
        model_consensus * 0.30 +
        market_clarity * 0.25 +
        data_quality * 0.20 +
        tactical_clarity * 0.15 +
        (1 - contradiction_penalty) * 0.10
    )

    if raw_score >= 0.92:  return "S"
    if raw_score >= 0.82:  return "A+"
    if raw_score >= 0.72:  return "A"
    if raw_score >= 0.62:  return "B+"
    if raw_score >= 0.50:  return "B"
    if raw_score >= 0.35:  return "C"
    return "D"
```

---

## Confidence ↔ Stake Relationship

Confidence ratings inform stake sizing:

| Confidence | Suggested Stake (% of bankroll) |
|------------|--------------------------------|
| S          | 2.0% – 3.0% (Kelly-guided) |
| A+         | 1.5% – 2.0% |
| A          | 1.0% – 1.5% |
| B+         | 0.5% – 1.0% |
| B          | 0.25% – 0.5% |
| C          | 0.0% – 0.25% (tracking only) |
| D          | 0.0% (NO BET) |

---

## Confidence Downgrade Triggers

Automatic one-level downgrade if ANY of:
- Model standard deviation > 8 percentage points
- Key player status unconfirmed
- Odds movement contradicts model direction
- Historical sample < 5 comparable matches
- Two or more agents flag HIGH risk
