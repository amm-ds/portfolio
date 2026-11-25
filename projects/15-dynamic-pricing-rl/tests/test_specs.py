"""Deterministic development-spec generation gates."""

from dynamic_pricing.specs import generate_specs


def test_specs_are_reproducible_balanced_and_stream_separated() -> None:
    first = generate_specs(["a", "b"], 9, seed=42, stream=0, prior_mean=-2.5, prior_sd=0.8)
    second = generate_specs(["a", "b"], 9, seed=42, stream=0, prior_mean=-2.5, prior_sd=0.8)
    other_stream = generate_specs(["a", "b"], 9, seed=42, stream=1, prior_mean=-2.5, prior_sd=0.8)
    assert first == second
    assert first != other_stream
    assert {rho: sum(spec.rho == rho for spec in first) for rho in (0.7, 1.0, 1.3)} == {
        0.7: 3,
        1.0: 3,
        1.3: 3,
    }
    assert all(-5.0 <= spec.epsilon <= -0.8 for spec in first)
    assert [spec.seed for spec in first] == list(range(9))
