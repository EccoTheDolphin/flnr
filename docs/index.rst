flnr API Reference
==================

.. toctree::
   :maxdepth: 1

.. automodule:: flnr
   :members:

.. automodule:: flnr.flnr
   :members:

Process Fate
------------

.. automodule:: flnr.fate
   :members:

Timeouts
--------

.. automodule:: flnr.timeouts
   :members:

Monitor Interfaces
------------------

.. automodule:: flnr.monitors
   :members:

Stream Bindings
---------------

.. autoclass:: flnr.InheritStdin

.. autoclass:: flnr.BindToParent

.. data:: flnr.INHERIT_STDIN
   :type: flnr.InheritStdin

   Inherit stdin directly from parent.

.. data:: flnr.BIND_TO_PARENT
   :type: flnr.BindToParent

   Bind child output directly to the corresponding parent stream.

   Output routed this way is not observed by output monitors.

Monitor Failures
----------------

.. automodule:: flnr.monitor_failure
   :members:

Exceptions
----------

.. automodule:: flnr.exceptions
   :members:

Host Control
------------

.. automodule:: flnr.host_control
   :members:

Command Tracing
---------------

.. autoclass:: flnr.CommandTracerProtocol
   :members:

.. autoclass:: flnr.CommandTracer
   :members:

.. autoclass:: flnr.command_tracing.LoggerLike
   :members:

.. autoclass:: flnr.command_tracing.EnvListing
   :members:

.. autofunction:: flnr.command_tracing.list_changed_environment

.. autofunction:: flnr.command_tracing.list_recreated_environment

.. autofunction:: flnr.command_tracing.list_selected_environment

.. autofunction:: flnr.command_tracing.list_no_environment

Monitoring Utilities
--------------------

.. automodule:: flnr.mu
   :members:

-----

.. rubric:: Epigraph

-- If a producer can outpace a consumer, something must grow, block, or die.
   (independently rediscovered, like most unpleasant truths)
