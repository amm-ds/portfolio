"""Typed shims for stub-less third-party imports — the project's single home
for missing-stubs ``type: ignore`` noise.

`datasets` and PyYAML ship no ``py.typed`` marker, so every direct import
would otherwise need its own ``# type: ignore[import-untyped]``. Re-exporting
the few names this project uses localizes the ignores to this one module, with
the reason stated once; every other module imports from here and stays
ignore-free. Pure re-exports — zero runtime effect.
"""

import yaml as _pyyaml  # type: ignore[import-untyped]  # PyYAML ships no stubs
from datasets import (  # type: ignore[import-untyped]  # datasets has no py.typed
    ClassLabel as ClassLabel,
)
from datasets import (
    Dataset as Dataset,
)
from datasets import (
    DatasetDict as DatasetDict,
)
from datasets import (
    Features as Features,
)
from datasets import (
    Value as Value,
)
from datasets import (
    load_dataset as load_dataset,
)
from datasets import (
    load_from_disk as load_from_disk,
)

# Thin aliases so callers never touch the untyped yaml module directly.
yaml_safe_load = _pyyaml.safe_load
yaml_safe_dump = _pyyaml.safe_dump

__all__ = [
    "ClassLabel",
    "Dataset",
    "DatasetDict",
    "Features",
    "Value",
    "load_dataset",
    "load_from_disk",
    "yaml_safe_dump",
    "yaml_safe_load",
]
