"""Public objects that describe subprocess outcome."""

from dataclasses import dataclass
from enum import Enum


class ProcessTerminationDecision(Enum):
    """Identify the supervisory decision **flnr** made while resolving outcome.

    This enum describes why **flnr** decided to intervene, or why no
    intervention was required. It is not a statement about the intrinsic cause
    of process exit. For the observed process status, inspect
    ``ProcessFate.returncode``. For how **flnr** carried that decision out,
    inspect ``ProcessTerminationMethod``.

    Attributes:
        NO_INTERVENTION:
            The process finished before **flnr** had to enforce any lifecycle
            action.

        TIMEOUT:
            The configured ``run`` timeout expired. **flnr** therefore decided
            that the process must be stopped.

        EXTERNAL_REQUEST:
            Host termination request was active, **flnr** attempted to
            gracefully terminate.

        INTERNAL_FAILURE:
            **flnr** observed an unrecoverable internal failure while
            supervising the process and therefore decided that the process must
            be stopped immediately.

    .. note::
        This value records **flnr**'s supervisory decision, not a claim about
        what the operating system process "really died from". For example, once
        the ``run`` timeout is breached, the decision remains ``TIMEOUT`` even
        if the process exits on its own before a requested signal takes effect.

    """

    NO_INTERVENTION = "no_intervention"
    TIMEOUT = "timeout"
    EXTERNAL_REQUEST = "external_request"
    INTERNAL_FAILURE = "internal_failure"

    def __str__(self) -> str:
        """Provide string representation of ``ProcessTerminationDecision``."""
        return self.value


class ProcessTerminationMethod(Enum):
    """Identify how **flnr** enforced process termination.

    When **flnr** decides that a process must be stopped, it resolves a
    termination method and carries execution through that stage.

    This value describes the enforcement path chosen by **flnr**. It is not a
    claim about what the process itself observed.

    Attributes:
        NONE:
            No enforcement was needed.

        TERMINATE:
            **flnr** resolved termination through graceful termination.

        KILL:
            **flnr** resolved termination through forced termination.

    """

    NONE = "none"
    TERMINATE = "terminate"
    KILL = "kill"

    def __str__(self) -> str:
        """Provide string representation of ``ProcessTerminationMethod``."""
        return self.value


@dataclass(frozen=True, slots=True)
class ProcessFate:
    """Represents subprocess outcome as resolved by **flnr**.

    A ``ProcessFate`` object combines three pieces of information:

    - the supervisory decision made by **flnr**
    - the termination method selected by **flnr**
    - the process return code observed by **flnr**, if available

    ``returncode`` may be ``None`` when **flnr** could not confirm process
    exit within the allowed observation window.
    """

    termination_decision: ProcessTerminationDecision
    termination_method: ProcessTerminationMethod
    returncode: int | None

    def __str__(self) -> str:
        """Provide string representation of ``ProcessFate``."""
        return (
            f"returncode={self.returncode}, "
            f"decision={self.termination_decision}, "
            f"method={self.termination_method}"
        )
