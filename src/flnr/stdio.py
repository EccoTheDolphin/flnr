"""Opt-in bindings for child IO streams."""

from typing import Final


class InheritStdin:
    """Marker type for inheriting child stdin from the parent stdin."""

    __slots__ = ()


class BindToParent:
    """Marker type for binding a child output stream to its parent stream."""

    __slots__ = ()


INHERIT_STDIN: Final[InheritStdin] = InheritStdin()
BIND_TO_PARENT: Final[BindToParent] = BindToParent()
