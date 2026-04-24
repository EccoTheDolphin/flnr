import io
import os
from collections.abc import Sequence
from pathlib import Path
from unittest.mock import patch

import pytest

import flnr
from tests._support.probes import FlushCall, TextIOProbe


def _run_stream_processing(
    data_in: Sequence[bytes], encoding: str, expected: str
) -> None:
    string_output = io.StringIO()
    out = flnr.TextOutputMonitor(sink=string_output, encoding=encoding)
    for data in data_in:
        out.process(data, 0)
    assert string_output.getvalue() == expected


def test_logger_default_behavior() -> None:
    default_output = io.StringIO()
    latin1_output = io.StringIO()
    rainbow_output = io.StringIO()
    default_logger = flnr.TextOutputMonitor(sink=default_output)
    latin1_logger = flnr.TextOutputMonitor(
        sink=latin1_output, encoding="latin-1"
    )
    rainbow_logger = flnr.TextOutputMonitor(
        sink=rainbow_output, encoding="utf-8"
    )
    for logger in [default_logger, latin1_logger, rainbow_logger]:
        logger.process(b"\xf0\x9f\x8c\x88", 0)
        logger.process(b"", 0)
    assert latin1_output.getvalue() == default_output.getvalue()
    assert latin1_output.getvalue() != rainbow_output.getvalue()


def test_logger_rainbow() -> None:
    _run_stream_processing([b"\xf0\x9f\x8c\x88", b""], "utf-8", "🌈")


def test_logger_rainbow_in_chunks() -> None:
    _run_stream_processing(
        [b"\xf0", b"\x9f", b"\x8c", b"\x88", b""], "utf-8", "🌈"
    )


def test_logger_rainbow_latin1() -> None:
    _run_stream_processing(
        [b"\xf0\x9f\x8c\x88", b""], "latin-1", "\xf0\x9f\x8c\x88"
    )


def test_logger_rainbow_latin1_tail() -> None:
    _run_stream_processing(
        [b"\xf0\x9f\x8c\x88tail", b""], "latin-1", "\xf0\x9f\x8c\x88tail"
    )


def test_logger_broken_rainbow_latin1() -> None:
    _run_stream_processing([b"\xf0\x9f\x8c", b""], "latin-1", "\xf0\x9f\x8c")


def test_logger_broken_rainbow_utf8() -> None:
    _run_stream_processing([b"\xf0\x9f\x8c", b""], "utf-8", "�")


def test_logger_broken_rainbow_utf8_partial() -> None:
    _run_stream_processing([b"\xf0", b"\x9f", b"\x8c", b""], "utf-8", "�")


def test_logger_broken_rainbow_with_tail_utf8() -> None:
    _run_stream_processing([b"\xf0\x9f\x8cbroken", b""], "utf-8", "�broken")


def test_logger_data_no_newline_no_flush() -> None:
    _run_stream_processing([b"no_newline"], "utf-8", "")


def test_logger_newline_normalization_lf() -> None:
    _run_stream_processing([b"line\n"], "utf-8", "line\n")


def test_logger_newline_normalization_crlf() -> None:
    _run_stream_processing([b"line\r\n"], "utf-8", "line\n")


def test_logger_newline_normalization_cr() -> None:
    _run_stream_processing([b"line\r"], "utf-8", "")


def test_logger_newline_normalization_cr_flushed() -> None:
    _run_stream_processing([b"line\r", b""], "utf-8", "line\r")


def test_logger_ils_buffer_limit() -> None:
    string_sink = io.StringIO()
    log_mon = flnr.TextOutputMonitor(sink=string_sink, ils_buffer_limit=3)
    log_mon.process(b"123456", 0)
    assert string_sink.getvalue() == "123456"
    log_mon.process(b"123", 0)
    assert string_sink.getvalue() == "123456"
    log_mon.process(b"x", 0)
    assert string_sink.getvalue() == "123456123x"
    log_mon.process(b"y", 0)
    assert string_sink.getvalue() == "123456123x"
    log_mon.on_disable(flnr.OutputMonitorDisableReason.ERROR, 0)
    assert string_sink.getvalue() == "123456123xy"


def test_logger_invalid_timestamp_base() -> None:
    error_msg = "timestamp_base must be finite non-negative real number or None"
    for value in [True, False, error_msg]:
        with pytest.raises(TypeError, match=error_msg):
            flnr.TextOutputMonitor(
                sink=io.StringIO(),
                timestamp_base=value,  # type: ignore[arg-type]
            )
    for value in [float("inf"), float("nan"), -1]:
        with pytest.raises(ValueError, match=error_msg):
            flnr.TextOutputMonitor(sink=io.StringIO(), timestamp_base=value)


def test_logger_invalid_timestamp_precision() -> None:
    error_msg = "timestamp_precision must be integer between 0 and 9 or None"
    for value in ["string", True, False, 1.0]:
        with pytest.raises(TypeError, match=error_msg):
            flnr.TextOutputMonitor(
                sink=io.StringIO(),
                timestamp_precision=value,  # type: ignore[arg-type]
            )
    for value in [-1, 10]:
        with pytest.raises(ValueError, match=error_msg):
            flnr.TextOutputMonitor(
                sink=io.StringIO(), timestamp_precision=value
            )


def test_logger_invalid_timestamp_base_noprecision() -> None:
    error_msg = (
        "timestamp_base is specified, but timestamp_precision is missing"
    )
    with pytest.raises(ValueError, match=error_msg):
        flnr.TextOutputMonitor(
            sink=io.StringIO(), timestamp_base=1.0, timestamp_precision=None
        )


def test_logger_timestamping_defaults() -> None:
    log_mon = flnr.TextOutputMonitor(sink=io.StringIO())
    assert log_mon.timestamp_precision is None
    assert log_mon.timestamp_base is None


def test_logger_disable_marker_default() -> None:
    log_mon = flnr.TextOutputMonitor(sink=io.StringIO())
    assert not log_mon.append_disable_marker


def test_logger_disable_marker_enabled() -> None:
    text_output = io.StringIO()

    with patch("flnr.mu.time.monotonic", return_value=10.0):
        log_mon = flnr.TextOutputMonitor(
            sink=text_output, append_disable_marker=True
        )
        assert log_mon.append_disable_marker
    log_mon.on_disable(flnr.OutputMonitorDisableReason.ERROR, 1)
    assert text_output.getvalue().splitlines() == [
        "",
        "[flnr] !! text output monitor disabled: error",
        "[flnr] !! monitor was created @ monotonic 10.0",
        "[flnr] !! end of watch @ monotonic 1",
    ]


@pytest.mark.parametrize("precision", [0, 3, 9])
@pytest.mark.parametrize("base", [None, 1.5])
def test_logger_timestamp_precision(precision: int, base: float | None) -> None:
    sink = io.StringIO()
    log_mon = flnr.TextOutputMonitor(
        sink=sink,
        encoding="utf-8",
        timestamp_precision=precision,
        timestamp_base=base,
    )
    ts = 1.625123
    flush_ts = ts + 2
    effective_ts1 = ts if base is None else ts - base
    effective_ts2 = flush_ts if base is None else flush_ts - base
    prefix1 = f"[{effective_ts1:.{precision}f}] "
    prefix2 = f"[{effective_ts2:.{precision}f}] "
    log_mon.process(b"data\n", ts)
    log_mon.process(b"line2", ts + 1)
    log_mon.on_disable(flnr.OutputMonitorDisableReason.EOF, flush_ts)
    assert sink.getvalue() == f"{prefix1}data\n{prefix2}line2"


@pytest.mark.parametrize("encoding", ["utf-8", "latin-1"])
def test_logger_encoding(test_resources: Path, encoding: str) -> None:
    input_file = test_resources / "data" / "invalid_utf8.txt"
    text_data = input_file.read_text(encoding=encoding, errors="replace")
    string_sink = io.StringIO()
    log_mon = flnr.TextOutputMonitor(sink=string_sink, encoding=encoding)
    log_mon.process(input_file.read_bytes(), 0)
    log_mon.process(b"", 0)
    assert text_data == string_sink.getvalue()


@pytest.mark.parametrize("auto_flush", [True, False])
def test_autoflush(test_resources: Path, auto_flush: bool) -> None:
    input_file = test_resources / "data" / "default.txt"
    if auto_flush:
        expected_flushes = len(input_file.read_text().splitlines())
    else:
        expected_flushes = 0
    with (
        Path(os.devnull).open("w") as null_file,
        patch.object(null_file, "flush", wraps=null_file.flush) as spy,
    ):
        log_mon = flnr.TextOutputMonitor(
            sink=null_file, encoding="latin-1", auto_flush=auto_flush
        )
        log_mon.process(input_file.read_bytes(), 0)
        log_mon.process(b"", 0)

        assert spy.call_count == expected_flushes


@pytest.mark.parametrize("auto_flush", [True, False])
def test_flush_on_disable(auto_flush: bool) -> None:
    probe = TextIOProbe()
    log_mon = flnr.TextOutputMonitor(
        sink=probe, encoding="latin-1", auto_flush=auto_flush
    )
    log_mon.process(b"string", 0)
    log_mon.on_disable(flnr.OutputMonitorDisableReason.EOF, 0)

    events = probe.getevents()
    assert isinstance(events[-1], FlushCall)
