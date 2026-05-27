# Reasoning Rules — Football Betting Intelligence System
# How each agent must structure its analytical reasoning.

---

## Reasoning Framework: CRISP-DM Adapted for Sports Betting

Each agent follows a structured reasoning pipeline:

### 1. DATA → OBSERVATION
- What does the raw data say?
- No interpretation yet — just facts.

### 2. OBSERVATION → PATTERN
- What patterns, trends, or anomalies are visible?
- Comparison against baselines / averages.

### 3. PATTERN → HYPOTHESIS
- What is the most likely explanation?
- What are alternative explanations?

### 4. HYPOTHESIS → TEST
- Does other data support or contradict this hypothesis?
- What would falsify this hypothesis?

### 5. TEST → CONCLUSION
- What is the calibrated probability estimate?
- What is the confidence level?
- What remains uncertain?

---

## Bayesian Updating Protocol

When agents receive new information, they must update their priors:

```
posterior_odds = prior_odds * likelihood_ratio
```

Agents should explicitly state:
1. Prior belief (before new information)
2. New evidence
3. Likelihood ratio (strength of evidence)
4. Posterior belief (updated estimate)

---

## Evidence Weighting Hierarchy

Evidence is ranked by reliability:

**TIER 1 (Highest Weight):**
- Closing line value (CLV) history
- Sharp money movement (confirmed by multiple books)
- xG data (10+ match sample)
- Verified injury to key player (confirmed by club)

**TIER 2 (Medium Weight):**
- Opening line vs. model fair value
- Tactical matchup analysis
- Historical H2H patterns (large sample)
- Referee statistical tendencies

**TIER 3 (Lower Weight):**
- Short-term form (≤5 matches)
- Public betting percentages
- Media narratives
- Social media sentiment

**TIER 4 (Minimal Weight / Noise):**
- Single-match anomalies
- Unverified rumors
- "Expert" opinion without data
- Fan sentiment

---

## Counterfactual Reasoning

For every key conclusion, agents must ask:

"If my conclusion is wrong, what would be the most likely reason?"

This must be documented in `contradictions` and `uncertainty_notes`.

---

## Base Rate Awareness

Before making any specific prediction, agents must reference the base rate:

- Home win rate in this league: ~X%
- Draw rate in this league: ~Y%
- Over 2.5 goals rate in this league: ~Z%

Specific predictions must be justified as deviations from base rates.

---

## Regression to the Mean

Agents must account for mean reversion:

- Extreme recent performance (over/under) is likely to regress
- The stronger the outlier, the stronger the expected regression
- Quantify: "Team A has overperformed xG by 4.2 goals in last 5 matches.
  Expected regression: ~60% of overperformance within next 5 matches."

---

## Small Sample Warning

When working with <10 matches of data:

- EXPLICITLY flag as small sample
- Widen confidence intervals
- Reduce weight in ensemble models
- Apply shrinkage toward league average

---

## Correlation ≠ Causation

Agents must distinguish:

- "Team A has won 7 of last 10 vs. Team B" → This is a statistic.
- "Team A has a tactical edge that explains this pattern" → This is analysis.
- "Team A will therefore likely win" → This is a hypothesis requiring testing.

---

## Market Efficiency Assumption

The DEFAULT assumption is that markets are efficient.

The burden of proof is on the analyst to demonstrate WHY the market is wrong.

This prevents overfitting and hindsight bias.
