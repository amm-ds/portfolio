"""Shared pytest config for portfolio-core.

Registers the hypothesis settings profiles used by the repo's property tests.
The default profile is untouched; the ``nightly`` profile raises the example
budget for the nightly workflow, which selects it with
``pytest --hypothesis-profile nightly -m hypothesis --hypothesis-seed <date>``.
Profiles are process-global once the plugin loads one, so a run that includes
this conftest applies the profile to hypothesis tests in other packages too
(e.g. projects/06-routing-optimization/tests).
"""

from hypothesis import settings

# ~10x the default 100 examples; no per-example deadline (free 2-vCPU
# runners are slow, and the point of the profile is volume, not speed).
settings.register_profile("nightly", max_examples=1000, deadline=None)
