import logging
import os

import pytest

import flnr
from flnr.command_tracing import (
    list_changed_environment,
    list_no_environment,
    list_selected_environment,
)
from tests._support.utils import PythonCmdBuilder


def _logged_message_lines(
    caplog: pytest.LogCaptureFixture,
    logger: logging.Logger,
) -> list[str]:
    records = [
        record for record in caplog.records if record.name == logger.name
    ]
    assert len(records) == 1
    assert isinstance(records[0].msg, str)
    assert records[0].args == ()
    message = records[0].getMessage()
    return message.splitlines()


def test_recipe_selected_env_vars(
    py_exec: PythonCmdBuilder,
    caplog: pytest.LogCaptureFixture,
    request: pytest.FixtureRequest,
) -> None:
    logger = logging.getLogger(request.node.nodeid)
    caplog.set_level(logging.INFO, logger=logger.name)
    host_env = os.environ.copy()
    child_env = {**host_env, "FLNR_VISIBLE_ENV": "visible"}
    cmd = tuple(py_exec("py_true.py"))

    tracer = flnr.CommandTracer(
        logger,
        env_listing=list_selected_environment(["FLNR_VISIBLE_ENV"]),
    )
    fate = flnr.run_ex(
        cmd,
        env=child_env,
        tracer=tracer,
    )

    assert fate.returncode == 0
    assert _logged_message_lines(caplog, logger) == [
        f"env FLNR_VISIBLE_ENV=visible {cmd[0]} {cmd[1]}",
    ]


def test_recipe_default(
    py_exec: PythonCmdBuilder,
    caplog: pytest.LogCaptureFixture,
    request: pytest.FixtureRequest,
) -> None:
    logger = logging.getLogger(request.node.nodeid)
    caplog.set_level(logging.INFO, logger=logger.name)
    host_env = os.environ.copy()
    child_env = {**host_env, "FLNR_VISIBLE_ENV": "visible"}
    cmd = tuple(py_exec("py_true.py"))

    tracer = flnr.CommandTracer(logger)
    fate = flnr.run_ex(
        cmd,
        env=child_env,
        tracer=tracer,
    )

    assert fate.returncode == 0
    assert _logged_message_lines(caplog, logger) == [
        f"{cmd[0]} {cmd[1]}",
    ]


def test_recipe_without_environment(
    py_exec: PythonCmdBuilder,
    caplog: pytest.LogCaptureFixture,
    request: pytest.FixtureRequest,
) -> None:
    logger = logging.getLogger(request.node.nodeid)
    caplog.set_level(logging.INFO, logger=logger.name)
    host_env = os.environ.copy()
    child_env = {**host_env, "FLNR_VISIBLE_ENV": "visible"}
    cmd = tuple(py_exec("py_true.py"))

    tracer = flnr.CommandTracer(logger, env_listing=list_no_environment)
    fate = flnr.run_ex(
        cmd,
        env=child_env,
        tracer=tracer,
    )

    assert fate.returncode == 0
    assert _logged_message_lines(caplog, logger) == [
        f"{cmd[0]} {cmd[1]}",
    ]


def test_recipe_for_changed_environment(
    py_exec: PythonCmdBuilder,
    caplog: pytest.LogCaptureFixture,
    request: pytest.FixtureRequest,
) -> None:
    logger = logging.getLogger(request.node.nodeid)
    caplog.set_level(logging.INFO, logger=logger.name)

    host_env = os.environ.copy()
    changed_value = "changed-visible"
    child_env = {**host_env, "FLNR_CHANGED_ENV": changed_value}
    cmd = tuple(py_exec("py_true.py"))
    tracer = flnr.CommandTracer(logger, env_listing=list_changed_environment)
    fate = flnr.run_ex(
        cmd,
        env=child_env,
        tracer=tracer,
    )

    assert fate.returncode == 0
    assert _logged_message_lines(caplog, logger) == [
        f"env FLNR_CHANGED_ENV={changed_value} {cmd[0]} {cmd[1]}",
    ]
