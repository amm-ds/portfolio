"""Track-level constants of the direct multi-horizon protocol (direct_multihorizon_v1).

The candidate roster (CANDIDATES / ML_SPARSE / COMPARISON_CANDIDATES), the
champion / floor / naive labels, the learner band-ladder levels, the
newsvendor cost assumptions and the protocol id. Pure literals — this module
is the leaf of the multistep module graph and imports nothing.
"""

PROTOCOL = "direct_multihorizon_v1"


# Quantile levels for the learner's forecast distribution.
QUANTILES_MS = (0.1, 0.5, 0.9)
# Sparse-band quantile ladder levels (over the training-window demand history).
LADDER_LEVELS = (0.5, 0.8, 0.9, 0.95)


# Newsvendor decision layer (wave 22): the order quantity is the forecast
# band's q-quantile (q in config.service_levels). Cost model is a DOCUMENTED
# ASSUMPTION (not a measured saving): holding 1.0 per ordered-but-unsold unit
# per day, stockout penalty 3.0 per unmet unit per day.
NEWSVENDOR_HOLDING_COST = 1.0
NEWSVENDOR_STOCKOUT_COST = 3.0
# The committed learner band ladder the dense-row quantiles interpolate.
BAND_LADDER_LEVELS = QUANTILES_MS


CANDIDATES = (
    "routed",
    "direct_hgb",
    "seasonal_naive",
    "zero",
    "croston",
    "sba",
    "tsb",
    "ma_28",
    "adida_sba",
    "adida_tsb",
    "hgb_tweedie",
    "hurdle_hgb",
    "lgbm_tweedie",
    "lgbm_poisson",
    "hurdle_lgbm",
    "peak_weighted_hgb",
    "ensemble_convex",
    "routed_reconciled",
)
# Peak-capable ML candidates the sparse-series router may pick (direct_hgb
# stays reserved for smooth/erratic series — the wave-19 routing finding).
# Wave 21 adds the LightGBM family and the peak-weighted hurdle; the same
# list serves the dense pool (direct_hgb + these candidates).
ML_SPARSE = (
    "hgb_tweedie",
    "hurdle_hgb",
    "lgbm_tweedie",
    "lgbm_poisson",
    "hurdle_lgbm",
    "peak_weighted_hgb",
)
# Candidates compared against the routed pipeline and the zero floor in the
# candidate-comparison / headline rows (the ML pool + the convex ensemble +
# the wave-22 hierarchy-anchored routed post-processing). routed_reconciled
# is comparison-only: it never enters the routing pool.
COMPARISON_CANDIDATES = (*ML_SPARSE, "ensemble_convex", "routed_reconciled")
CHAMPION = "routed"
FLOOR = "seasonal_naive"
NAIVE = "zero"
