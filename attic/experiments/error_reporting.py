from collections.abc import Sequence

import flnr


class Melchior(flnr.EnvironmentMonitor):
    def __init__(self) -> None:
        super().__init__(period=1)

    def on_start(self, _: int, __: Sequence[str]) -> None:
        pass

    def observe(self, _: int) -> None:
        pass

    def on_end(self, _: flnr.ProcessFate) -> None:
        err_msg = "Magi 1"
        raise RuntimeError(err_msg)


class Balthasar(flnr.EnvironmentMonitor):
    def __init__(self) -> None:
        super().__init__(period=1)

    def on_start(self, _: int, __: Sequence[str]) -> None:
        pass

    def observe(self, _: int) -> None:
        err_msg = "Magi 2"
        raise RuntimeError(err_msg)

    def on_end(self, _: flnr.ProcessFate) -> None:
        pass


class Casper(flnr.EnvironmentMonitor):
    def __init__(self) -> None:
        super().__init__(period=1)

    def on_start(self, _: int, __: Sequence[str]) -> None:
        err_msg = "Magi 3"
        raise RuntimeError(err_msg)

    def observe(self, _: int) -> None:
        pass

    def on_end(self, _: flnr.ProcessFate) -> None:
        pass


class Eva01(flnr.OutputMonitor):
    def process(self, _: bytes, ts: float) -> None:
        err_msg = f"fatal error at {ts}"
        raise RuntimeError(err_msg)

    def on_disable(self, _: flnr.OutputMonitorDisableReason, __: float) -> None:
        pass


class Eva02(flnr.OutputMonitor):
    def process(self, _: bytes, __: float) -> None:
        pass

    def on_disable(self, _: flnr.OutputMonitorDisableReason, ts: float) -> None:
        err_msg = f"offline at {ts}"
        raise RuntimeError(err_msg)


try:
    flnr.run_ex(
        ["bash", "-c", "echo Disgusting ; sleep 2"],
        environment_monitors=[Melchior(), Balthasar(), Casper()],
        stdout_monitors=[Eva01()],
        stderr_monitors=[Eva02()],
        check=False,
        merge_std_streams=False,
    )
except flnr.MonitorFailedError as ex:
    print(ex)
