"""Task contract: registry shape, category rules and impl coverage."""

from data_engineering.engines import adapter_names
from data_engineering.tasks import NA_IMPLS, TASKS, TASKS_BY_NAME


def test_registry_shape() -> None:
    """10 tasks adapted from the canonical engine-benchmark dimensions."""
    assert len(TASKS) == 10
    names = [t.name for t in TASKS]
    assert len(names) == len(set(names)), "task names must be unique"
    assert names == [
        "read_parquet",
        "read_csv",
        "groupby",
        "join",
        "window",
        "filter",
        "strings_groupby",
        "distinct_sort",
        "write_parquet",
        "partitioned_read",
    ]
    assert TASKS_BY_NAME.keys() == set(names)


def test_every_task_declares_all_engines() -> None:
    """One implementation per registered engine, minus the honest n/a pairs."""
    for task in TASKS:
        expected = set(adapter_names()) - set(NA_IMPLS.get(task.name, ()))
        assert set(task.impls) == expected, task.name
        for engine, impl in task.impls.items():
            assert callable(impl), f"{task.name}/{engine} impl not callable"


def test_na_impls_are_documented_gaps() -> None:
    """Only write_parquet/sqlite is n/a, and the reason is the missing writer."""
    assert NA_IMPLS == {"write_parquet": ("sqlite",)}
    task = TASKS_BY_NAME["write_parquet"]
    assert "sqlite" not in task.impls
    assert "sqlite" in adapter_names(), "n/a must reference a registered engine"


def test_category_rules() -> None:
    """IO category is exactly the cold-measurable set; compute is the rest."""
    io_tasks = {t.name for t in TASKS if t.category == "io"}
    compute_tasks = {t.name for t in TASKS if t.category == "compute"}
    assert io_tasks == {"read_parquet", "read_csv", "write_parquet", "partitioned_read"}
    assert compute_tasks == {
        "groupby",
        "join",
        "window",
        "filter",
        "strings_groupby",
        "distinct_sort",
    }
    assert io_tasks | compute_tasks == {t.name for t in TASKS}
    for task in TASKS:
        assert task.cold_measurable == (task.category == "io")
        assert task.description, f"{task.name}: missing description"
