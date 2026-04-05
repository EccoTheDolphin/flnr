import io
import os
from collections.abc import Sequence
from pathlib import Path
from unittest.mock import patch

import pytest

from tests.lib.utils import TextOutputMonitor


def _run_stream_processing(
    data_in: Sequence[bytes], encoding: str, expected: str
) -> None:
    string_output = io.StringIO()
    out = TextOutputMonitor(sink=string_output, encoding=encoding)
    for data in data_in:
        out.process(data, 0)
    assert string_output.getvalue() == expected


def test_logger_default_behavior() -> None:
    default_output = io.StringIO()
    latin1_output = io.StringIO()
    rainbow_output = io.StringIO()
    default_logger = TextOutputMonitor(sink=default_output)
    latin1_logger = TextOutputMonitor(sink=latin1_output, encoding="latin-1")
    rainbow_logger = TextOutputMonitor(sink=rainbow_output, encoding="utf-8")
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


@pytest.mark.parametrize("encoding", ["utf-8", "latin-1"])
def test_logger_encoding(test_resources: Path, encoding: str) -> None:
    input_file = test_resources / "data" / "invalid_utf8.txt"
    text_data = input_file.read_text(encoding=encoding, errors="replace")
    string_sink = io.StringIO()
    log_mon = TextOutputMonitor(sink=string_sink, encoding=encoding)
    log_mon.process(input_file.read_bytes(), 0)
    log_mon.process(b"", 0)
    assert text_data == string_sink.getvalue()


@pytest.mark.parametrize("auto_flush", [True, False])
def test_autoflush(test_resources: Path, auto_flush: bool) -> None:
    input_file = test_resources / "data" / "miami_nights.txt"
    if auto_flush:
        expected_flushes = len(input_file.read_text().splitlines())
    else:
        expected_flushes = 0
    with (
        Path(os.devnull).open("w") as null_file,
        patch.object(null_file, "flush", wraps=null_file.flush) as spy,
    ):
        log_mon = TextOutputMonitor(
            sink=null_file, encoding="latin-1", auto_flush=auto_flush
        )
        log_mon.process(input_file.read_bytes(), 0)
        log_mon.process(b"", 0)

        assert spy.call_count == expected_flushes
