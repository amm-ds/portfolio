"""Policy selection must follow revenue minus send cost at the budget, never Qini."""

from uplift_experimentation.evaluate import select_recommended_policy


def test_selection_picks_highest_budget_value_not_best_qini() -> None:
    # Adversarial input shaped like the real ladder: the response model has the
    # best Qini (13.01 vs 12.03 — see README) but the LOWEST revenue minus send
    # cost at the 25% budget. A Qini-based rule would pick the response model;
    # the stated rule must pick the T-learner. (Deliberately broken variant:
    # replacing the key with max-Qini selection would fail this assertion.)
    budget_profits = {
        "random": 4026.0,
        "x_learner": 4564.0,
        "response_model": 4881.0,
        "t_learner": 6838.0,
    }
    assert select_recommended_policy(budget_profits) == "t_learner"


def test_selection_excludes_reference_curves() -> None:
    # treat-everyone realizes full incremental conversions at any fraction and
    # random is a baseline: neither is a budgetable targeting strategy, so even
    # overwhelming values for them must not win the recommendation.
    budget_profits = {
        "random": 1e9,
        "treat-everyone": 1e12,
        "t_learner": 6838.0,
    }
    assert select_recommended_policy(budget_profits) == "t_learner"
