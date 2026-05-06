"""Environment listing helpers for command tracers."""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass


def _freeze_variables(variables: Sequence[str]) -> tuple[str, ...]:
    if isinstance(variables, (str, bytes, bytearray, memoryview)):
        error_msg = "variables must be a sequence of environment names"
        raise TypeError(error_msg)

    frozen = tuple(variables)
    for variable in frozen:
        if not isinstance(variable, str):
            error_msg = "variables must contain only strings"
            raise TypeError(error_msg)
        if not variable:
            error_msg = "environment variable name must not be empty"
            raise ValueError(error_msg)

    return tuple(dict.fromkeys(frozen))


@dataclass(frozen=True, slots=True)
class EnvListing:
    """Environment rendering instructions for command recipes.

    ``EnvListing`` is returned by command tracer environment-listing callbacks.
    It describes what the renderer should include in the command recipe.

    ``variables`` are environment assignments to render, in order.

    ``clear_environment`` means the recipe should start from an empty
    environment before applying ``variables``.

    ``removed_variables`` are inherited environment variable names to remove
    from the rendered recipe. Renderers ignore this field when
    ``clear_environment`` is true.

    ``missing_variables`` are names requested by the listing callback but absent
    from the child environment. They are reported by ``CommandTracer`` as
    missing, not rendered as assignments.
    """

    variables: tuple[tuple[str, str], ...] = ()
    clear_environment: bool = False
    removed_variables: tuple[str, ...] = ()
    missing_variables: tuple[str, ...] = ()


def list_no_environment(
    child_env: Mapping[str, str],
    host_env: Mapping[str, str],
) -> EnvListing:
    """List no environment variables."""
    del child_env, host_env
    return EnvListing()


def list_changed_environment(
    child_env: Mapping[str, str],
    host_env: Mapping[str, str],
) -> EnvListing:
    """List child environment values changed from the host process environment.

    Unchanged host process environment variables are not listed. Host process
    variables missing from the child environment are listed by name, without
    their values.
    """
    return EnvListing(
        variables=tuple(
            (key, value)
            for key, value in child_env.items()
            if host_env.get(key) != value
        ),
        removed_variables=tuple(
            key for key in host_env if key not in child_env
        ),
    )


def list_recreated_environment(
    child_env: Mapping[str, str],
    host_env: Mapping[str, str],
) -> EnvListing:
    """List the complete child environment from an empty environment base."""
    del host_env
    return EnvListing(
        variables=tuple(child_env.items()),
        clear_environment=True,
    )


def list_selected_environment(
    variables: Sequence[str],
) -> Callable[[Mapping[str, str], Mapping[str, str]], EnvListing]:
    """Create a helper that lists selected environment variables.

    Tracer-enabled call sites should not select secret variables for display.
    """
    names = _freeze_variables(variables)

    def list_selected_env(
        child_env: Mapping[str, str],
        host_env: Mapping[str, str],
    ) -> EnvListing:
        del host_env
        return EnvListing(
            variables=tuple(
                (name, child_env[name]) for name in names if name in child_env
            ),
            missing_variables=tuple(
                name for name in names if name not in child_env
            ),
        )

    return list_selected_env
