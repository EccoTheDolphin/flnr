import random
from collections.abc import Sequence

import pytest

from flnr import IncrementalLineSplitter


def _run_basic_scenario(
    data_in: Sequence[bytes], expected: Sequence[bytes]
) -> None:
    ils = IncrementalLineSplitter()
    for data in data_in:
        result = ils.feed(data)
    assert result == expected


def test_empty_chunk_returns_nothing() -> None:
    _run_basic_scenario([b""], [])


def test_complete_line_returns_line() -> None:
    _run_basic_scenario([b"a\n"], [b"a\n"])


def test_partial_line_buffered_not_returned() -> None:
    _run_basic_scenario([b"a"], [])


def test_partial_followed_by_complete_returns_complete_only() -> None:
    _run_basic_scenario([b"a\nb"], [b"a\n"])


def test_complete_then_partial_buffers_partial() -> None:
    _run_basic_scenario([b"a\n", b"b"], [])


def test_two_complete_lines_in_one_chunk() -> None:
    _run_basic_scenario([b"a\nb\n"], [b"a\n", b"b\n"])


def test_empty_chunk_flushes_buffered_partial_line() -> None:
    _run_basic_scenario([b"a\nb", b""], [b"b"])


def test_no_output_after_flush() -> None:
    _run_basic_scenario([b"a\nb", b"", b""], [])


def test_single_empty_line() -> None:
    _run_basic_scenario([b"\n"], [b"\n"])


def test_empty_lines() -> None:
    _run_basic_scenario([b"\n\n\n"], [b"\n", b"\n", b"\n"])


@pytest.mark.report_tracemalloc
@pytest.mark.report_duration
def test_memory_pressure() -> None:
    random.seed(42)
    ils = IncrementalLineSplitter()
    for _ in range(8 * 1024):
        ils.feed(b"z*" * random.randrange(8 * 1024 + 1) + b"\n")
        if random.choice([True, False]):
            for __ in range(random.randrange(1024)):
                ils.feed(b"x")
    # the buffer should not grow too much
    assert len(ils.buf) < 1024 * 1024
