from __future__ import annotations

from contextvars import ContextVar
from visionqc.bootstrap import ApplicationContext

_context: ContextVar[ApplicationContext | None] = ContextVar("visionqc_application_context", default=None)


def set_application_context(context: ApplicationContext) -> None:
    _context.set(context)


def get_application_context() -> ApplicationContext:
    context = _context.get()
    if context is None:
        raise RuntimeError("VisionQC application context has not been initialized")
    return context
