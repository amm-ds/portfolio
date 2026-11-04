"""Task contract: registry shape, category rules and impl coverage."""

from data_engineering.engines import adapter_names
from data_engineering.tasks import TASKS, TASKS_BY_NAME


def test_registry_shape() -> None:
    """8 tasks adapted from the canonical engine-benchmark dimensions."""
    assert len(TASKS) == 8
    names = [t.name for t in TASKS]
    assert len(names) == len(set(names)), "task names must be unique"
    assert names == [
        "read_parquet",
        "read_csv",
        "groupby",
        "join",
        "window",
        "filter",
        "write_parquet",
        "partitioned_read",
    ]
    assert TASKS_BY_NAME.keys() == set(names)


def test_every_task_declares_all_engines() -> None:
    """One implementation per registered engine, per task."""
    for task in TASKS:
        assert set(task.impls) == set(adapter_names()), task.name
        for engine, impl in task.impls.items():
            assert callable(impl), f"{task.name}/{engine} impl not callable"


def test_category_rules() -> None:
    """IO category is exactly the cold-measurable set; compute is the rest."""
    io_tasks = {t.name for t in TASKS if t.category == "io"}
    compute_tasks = {t.name for t in TASKS if t.category == "compute"}
    assert io_tasks == {"read_parquet", "read_csv", "write_parquet", "partitioned_read"}
    assert compute_tasks == {"groupby", "join", "window", "filter"}
    assert io_tasks | compute_tasks == {t.name for t in TASKS}
    for task in TASKS:
        assert task.cold_measurable == (task.category == "io")
        assert task.description, f"{task.name}: missing description"
