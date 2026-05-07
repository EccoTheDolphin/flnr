import pytest

from flnr.command_tracing import (
    list_changed_environment,
    list_no_environment,
    list_selected_environment,
)


def test_list_no_environment_ignores_child_and_host_env() -> None:
    listing = list_no_environment(
        {"VISIBLE": "visible"},
        {"SECRET": "secret"},
    )

    assert listing.variables == ()
    assert listing.removed_variables == ()
    assert listing.missing_variables == ()


def test_list_selected_environment_validation() -> None:
    listing = list_selected_environment(["A", "A"])({"A": "value"}, {})
    assert listing.variables == (("A", "value"),)

    with pytest.raises(TypeError, match="sequence of environment names"):
        list_selected_environment("PATH")

    with pytest.raises(TypeError, match="contain only strings"):
        list_selected_environment(["PATH", 42])  # type: ignore[list-item]

    with pytest.raises(ValueError, match="must not be empty"):
        list_selected_environment([""])


def test_changed_environment_reports_removed_names_without_values() -> None:
    listing = list_changed_environment(
        {"PATH": "/usr/bin", "VISIBLE": "changed"},
        {
            "PATH": "/usr/bin",
            "REMOVED_SECRET": "secret",
            "VISIBLE": "old",
        },
    )

    assert listing.variables == (("VISIBLE", "changed"),)
    assert listing.removed_variables == ("REMOVED_SECRET",)
