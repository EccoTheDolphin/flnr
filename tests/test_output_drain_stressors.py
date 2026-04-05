import io
import sys
from collections.abc import Sequence

import pytest

import flnr
from tests.lib.utils import PythonCmdBuilder, TextOutputMonitor

SHAPES = ["num", "num-", "8k", "8k-"]
FLUSH = ["flush", "noflush"]

LARGE_DATASET_SIZE = 1024 * 1024 * 5


class _BinaryOutputStressorImpl(flnr.OutputMonitor):
    def __init__(self, sink: io.IOBase) -> None:
        self.sink = sink

    def process(self, data: bytes, _: float) -> None:
        self.sink.write(data)


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
    flnr.run_shell_ex(
        py_exec("drain_stressor.py", str(size), shape, flush),
        stdout_observers=stdout_monitors or [],
        stderr_observers=stderr_monitors or [],
        merge_std_streams=stderr_merged,
    )


@pytest.mark.report_tracemalloc
@pytest.mark.report_duration
@pytest.mark.parametrize("shape", SHAPES)
@pytest.mark.parametrize("flush", FLUSH)
def test_reader_stressor_stderr_separate(
    py_exec: PythonCmdBuilder,
    shape: str,
    flush: str,
) -> None:
    _run_stressor(
        py_exec,
        LARGE_DATASET_SIZE,
        shape=shape,
        flush=flush,
        stderr_merged=False,
    )


@pytest.mark.report_tracemalloc
@pytest.mark.report_duration
@pytest.mark.parametrize("shape", SHAPES)
@pytest.mark.parametrize("flush", FLUSH)
def test_reader_stressor_stderr_merged(
    py_exec: PythonCmdBuilder,
    shape: str,
    flush: str,
) -> None:
    _run_stressor(
        py_exec,
        LARGE_DATASET_SIZE,
        shape=shape,
        flush=flush,
        stderr_merged=True,
    )


@pytest.mark.report_tracemalloc
@pytest.mark.report_duration
@pytest.mark.parametrize("shape", SHAPES)
def test_stressor_large_with_text_observer_stderr_merged(
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
            TextOutputMonitor(sink=string_sink, encoding="utf-8"),
            _BinaryOutputStressorImpl(sink=bin_sink),
        ],
        stderr_merged=True,
    )
    binary_representation = bin_sink.getvalue()
    assert len(binary_representation) == LARGE_DATASET_SIZE * 2
    # it seems that the procedure below causes github runner to hang. For
    # now this check is disabled for windows platform
    if not sys.platform.startswith("win"):
        # this trick ensures that the text representation has normalized line
        # endings
        as_text = "".join(
            binary_representation.decode("utf-8").splitlines(keepends=True)
        )
        assert string_sink.getvalue() == as_text


@pytest.mark.parametrize("shape", SHAPES)
@pytest.mark.parametrize(
    "size", [0, 1023, 1024, 1025, 4095, 4096, 4097, 65535, 65536, 65537]
)
def test_stressor_with_bin_observer(
    py_exec: PythonCmdBuilder, shape: str, size: int
) -> None:
    bin_sink = io.BytesIO()
    _run_stressor(
        py_exec,
        size,
        shape=shape,
        flush="noflush",
        stdout_monitors=[_BinaryOutputStressorImpl(sink=bin_sink)],
    )
    assert len(bin_sink.getvalue()) == size
