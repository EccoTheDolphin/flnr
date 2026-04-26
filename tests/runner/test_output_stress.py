import io
import os
from collections.abc import Sequence

import pytest

import flnr
from tests._support.asserts import assert_blob_eq
from tests._support.probes import (
    OutputMonitorProbe,
)
from tests._support.utils import PythonCmdBuilder

SHAPES = ["num", "num-", "8k", "8k-"]
FLUSH = ["flush", "noflush"]

LARGE_DATASET_SIZE = 1024 * 1024 * 5


def _validate_output_probe(probe: OutputMonitorProbe, data_size: int) -> None:
    assert probe.n_processed_bytes == data_size
    if data_size > 0:
        assert probe.n_process_calls > 0
    else:
        assert probe.n_process_calls == 0
    assert probe.stop_reason == flnr.OutputMonitorDisableReason.EOF
    if data_size > 0:
        assert probe.ts_last_process is not None
        assert probe.ts_stop is not None
        assert probe.ts_last_process <= probe.ts_stop
    else:
        assert probe.ts_last_process is None


def _run_stressor(
    py_exec: PythonCmdBuilder,
    size: int,
    *,
    shape: str,
    flush: str,
    stdout_monitors: Sequence[flnr.OutputMonitor] | None = None,
    stderr_monitors: Sequence[flnr.OutputMonitor] | None = None,
    stderr_merged: bool = False,
) -> None:
    flnr.run_ex(
        py_exec("drain_stressor.py", str(size), shape, flush),
        stdout_monitors=stdout_monitors or [],
        stderr_monitors=stderr_monitors or [],
        merge_std_streams=stderr_merged,
    )


@pytest.mark.stress
@pytest.mark.report_tracemalloc
@pytest.mark.report_duration
@pytest.mark.parametrize("shape", SHAPES)
@pytest.mark.parametrize("flush", FLUSH)
@pytest.mark.parametrize("probe", [True, False])
def test_stderr_separate(
    py_exec: PythonCmdBuilder, shape: str, flush: str, probe: bool
) -> None:
    stdout_monitors: list[flnr.OutputMonitor] = []
    stderr_monitors: list[flnr.OutputMonitor] = []
    stdout_probe = None
    stderr_probe = None
    if probe:
        stdout_probe = OutputMonitorProbe(sink=None)
        stderr_probe = OutputMonitorProbe(sink=None)
        stdout_monitors.append(stdout_probe)
        stderr_monitors.append(stderr_probe)
    _run_stressor(
        py_exec,
        LARGE_DATASET_SIZE,
        shape=shape,
        flush=flush,
        stderr_merged=False,
        stdout_monitors=stdout_monitors,
        stderr_monitors=stderr_monitors,
    )
    if stdout_probe is not None:
        _validate_output_probe(stdout_probe, LARGE_DATASET_SIZE)
    if stderr_probe is not None:
        _validate_output_probe(stderr_probe, LARGE_DATASET_SIZE)


@pytest.mark.stress
@pytest.mark.report_tracemalloc
@pytest.mark.report_duration
@pytest.mark.parametrize("shape", SHAPES)
@pytest.mark.parametrize("flush", FLUSH)
@pytest.mark.parametrize("probe", [True, False])
def test_stderr_merged(
    py_exec: PythonCmdBuilder, shape: str, flush: str, probe: bool
) -> None:
    stdout_monitors: list[flnr.OutputMonitor] = []
    stdout_probe = None
    if probe:
        stdout_probe = OutputMonitorProbe(sink=None)
        stdout_monitors.append(stdout_probe)
    _run_stressor(
        py_exec,
        LARGE_DATASET_SIZE,
        shape=shape,
        flush=flush,
        stderr_merged=True,
        stdout_monitors=stdout_monitors,
    )
    if stdout_probe is not None:
        _validate_output_probe(stdout_probe, 2 * LARGE_DATASET_SIZE)


@pytest.mark.stress
@pytest.mark.report_tracemalloc
@pytest.mark.report_duration
@pytest.mark.parametrize("shape", SHAPES)
def test_stressor_large_with_text_monitor_stderr_merged(
    py_exec: PythonCmdBuilder, shape: str
) -> None:
    bin_sink = io.BytesIO()
    string_sink = io.StringIO()
    _run_stressor(
        py_exec,
        LARGE_DATASET_SIZE,
        shape=shape,
        flush="noflush",
        stdout_monitors=[
            flnr.TextOutputMonitor(sink=string_sink, encoding="utf-8"),
            OutputMonitorProbe(sink=bin_sink),
        ],
        stderr_merged=True,
    )
    binary_representation = bin_sink.getvalue()
    assert len(binary_representation) == LARGE_DATASET_SIZE * 2
    raw_lines = binary_representation.decode("utf-8").splitlines(keepends=True)
    normalized_lines = [rline.removesuffix(os.linesep) for rline in raw_lines]
    normalized_text = "\n".join(normalized_lines)
    text_output = string_sink.getvalue()
    # note: '\n' at the end is removed to avoid corner cases where the original
    # text streams ends with newline, but processed binary contents does not
    # have one because of join
    assert_blob_eq(text_output.removesuffix("\n"), normalized_text)


@pytest.mark.stress
@pytest.mark.parametrize("shape", SHAPES)
@pytest.mark.parametrize(
    "size", [0, 1023, 1024, 1025, 4095, 4096, 4097, 65535, 65536, 65537]
)
def test_stressor_with_binary_probe(
    py_exec: PythonCmdBuilder, shape: str, size: int
) -> None:
    bin_sink = io.BytesIO()
    binary_probe = OutputMonitorProbe(sink=bin_sink)
    _run_stressor(
        py_exec,
        size,
        shape=shape,
        flush="noflush",
        stdout_monitors=[binary_probe],
    )
    assert len(bin_sink.getvalue()) == size
    _validate_output_probe(binary_probe, size)
