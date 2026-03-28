"""Configuration constants for the seven-factor Market Selection Engine.

All learnable constants live here. Phase 4+ EWA updates will tune FACTOR_WEIGHTS
via live PnL without touching scorer.py or filters.py.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Factor weights — must sum to 1.0
# ---------------------------------------------------------------------------

FACTOR_WEIGHTS: dict[str, float] = {
    "category_edge": 0.20,
    "spread_opportunity": 0.20,
    "volume": 0.15,
    "competition": 0.15,
    "reward_apr": 0.15,
    "adverse_selection": 0.10,
    "time_to_resolution": 0.05,
}

assert abs(sum(FACTOR_WEIGHTS.values()) - 1.0) < 1e-9, (
    f"FACTOR_WEIGHTS must sum to 1.0, got {sum(FACTOR_WEIGHTS.values())}"
)

# ---------------------------------------------------------------------------
# Category-level edge prior (from Jon-Becker 72.1M trade analysis)
# Higher value = more maker edge structurally available in this category
# ---------------------------------------------------------------------------

CATEGORY_EDGE: dict[str, float] = {
    "Crypto": 0.70,
    "Sports": 0.65,
    "Politics": 0.55,
    "Finance": 0.60,
    "Entertainment": 0.50,
    "Science": 0.45,
    "Business": 0.55,
    "Culture": 0.50,
    "Tech": 0.60,
    "World": 0.50,
    "Other": 0.45,
}

CATEGORY_EDGE_DEFAULT: float = 0.50

# ---------------------------------------------------------------------------
# Adverse selection prior (category-level informed-trading probability)
# Higher value = more adverse selection risk; used as-is as a [0,1] score
# ---------------------------------------------------------------------------

ADVERSE_SELECTION_PRIOR: dict[str, float] = {
    "Crypto": 0.75,
    "Sports": 0.55,
    "Politics": 0.70,
    "Finance": 0.65,
    "Entertainment": 0.45,
    "Science": 0.50,
    "Business": 0.60,
    "Culture": 0.45,
    "Tech": 0.65,
    "World": 0.60,
    "Other": 0.55,
}

ADVERSE_SELECTION_DEFAULT: float = 0.60

# ---------------------------------------------------------------------------
# Gate thresholds (hard filters; markets below these are excluded)
# ---------------------------------------------------------------------------

MIN_VOLUME_24H: float = 500.0          # 24h volume in USD
MIN_SPREAD: float = 0.005              # minimum BBO spread (probability units)
MIN_DAYS_TO_RESOLUTION: float = 1.0   # markets resolving in < 1 day are excluded
MAX_SPREAD_REFERENCE: float = 0.10    # spread at or above this clips spread_score to 1.0

# ---------------------------------------------------------------------------
# Scoring parameters
# ---------------------------------------------------------------------------

LONGSHOT_BONUS_MAX: float = 0.15      # maximum bonus added to composite for longshot markets
LONGSHOT_THRESHOLD: float = 0.35      # mid_price below this receives a bonus
TIME_SCORE_CENTER_DAYS: float = 14.0  # Gaussian peak: markets resolving in ~14 days
COMPETITION_SPREAD_THRESHOLD: float = 0.03  # bid value threshold for non-trivial order proxy
TARGET_REWARD_APR: float = 1.0        # reward rate at which reward_apr_score = 1.0
NEGRISK_PENALTY: float = 0.85         # composite multiplier for NegRisk multi-outcome markets
