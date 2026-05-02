from tests._support.tracing import TraceEvent


class EventSystem:
    SUPERVISED_GREETED = TraceEvent()
    SUPERVISED_SPAWNED_DESCENDANT = TraceEvent()
    SUPERVISED_RELEASED_STDO = TraceEvent()
    SUPERVISED_CLOSING = TraceEvent()
    DESCENDANT_GREETED = TraceEvent()
    DESCENDANT_TICKED_FIRST = TraceEvent()
    DESCENDANT_TICKED_5 = TraceEvent()
    DESCENDANT_TICKED_ALL = TraceEvent()
    DESCENDANT_DATA_END = TraceEvent()
    DESCENDANT_SAID_BYE = TraceEvent()
    DESCENDANT_RELEASED_STDO = TraceEvent()
