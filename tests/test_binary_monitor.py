import io

import flnr


def test_binary_output_monitor() -> None:
    output_bin = io.BytesIO()
    bin_mon = flnr.BinaryOutputMonitor(sink=output_bin)
    bin_mon.process(b"abcdef", 0)
    assert output_bin.getvalue() == b"abcdef"
    bin_mon.process(b"a", 0)
    assert output_bin.getvalue() == b"abcdefa"
    bin_mon.on_disable(flnr.OutputMonitorDisableReason.EOF, 0)
    assert output_bin.getvalue() == b"abcdefa"
