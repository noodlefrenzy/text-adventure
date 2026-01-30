"""
telemetry.py

PURPOSE: OpenTelemetry initialization and tracer management.
DEPENDENCIES: opentelemetry-api, opentelemetry-sdk, opentelemetry-exporter-otlp (all optional)

ARCHITECTURE NOTES:
Provides graceful degradation when otel packages are not installed.
Uses a module-level tracer provider that can be initialized once at startup.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from text_adventure.config import OpenTelemetrySettings

logger = logging.getLogger(__name__)

# Global state for the tracer provider
_initialized = False
_tracer_provider: object | None = None


@runtime_checkable
class Span(Protocol):
    """Protocol for span interface."""

    def __enter__(self) -> Span: ...
    def __exit__(self, *args: object) -> None: ...
    def set_attribute(self, key: str, value: object) -> None: ...
    def set_status(self, status: object) -> None: ...
    def record_exception(self, exception: BaseException) -> None: ...
    def add_event(self, name: str, attributes: dict[str, object] | None = None) -> None: ...


@runtime_checkable
class Tracer(Protocol):
    """Protocol for tracer interface."""

    def start_as_current_span(self, name: str, **kwargs: object) -> Span: ...
    def start_span(self, name: str, **kwargs: object) -> Span: ...


class NoOpSpan:
    """A no-op span for when telemetry is disabled."""

    def __enter__(self) -> Span:
        return self

    def __exit__(self, *args: object) -> None:
        pass

    def set_attribute(self, key: str, value: object) -> None:  # noqa: ARG002
        pass

    def set_status(self, status: object) -> None:  # noqa: ARG002
        pass

    def record_exception(self, exception: BaseException) -> None:  # noqa: ARG002
        pass

    def add_event(  # noqa: ARG002
        self, name: str, attributes: dict[str, object] | None = None
    ) -> None:
        pass


class NoOpTracer:
    """A no-op tracer for when telemetry is disabled or packages missing."""

    def start_as_current_span(
        self,
        name: str,  # noqa: ARG002
        **kwargs: object,  # noqa: ARG002
    ) -> Span:
        return NoOpSpan()

    def start_span(
        self,
        name: str,  # noqa: ARG002
        **kwargs: object,  # noqa: ARG002
    ) -> Span:
        return NoOpSpan()


class LazyTracer:
    """
    A tracer that defers actual tracer lookup until span creation.

    This allows modules to call get_tracer() at import time, before
    init_telemetry() is called. The real tracer is resolved lazily
    when spans are actually created.
    """

    def __init__(self, name: str) -> None:
        self._name = name

    def _get_real_tracer(self) -> Tracer:
        """Get the real tracer, or NoOpTracer if not initialized."""
        if not _initialized or _tracer_provider is None:
            return NoOpTracer()

        try:
            from opentelemetry import trace

            return trace.get_tracer(self._name)  # type: ignore[return-value]
        except ImportError:
            return NoOpTracer()

    def start_as_current_span(self, name: str, **kwargs: object) -> Span:
        return self._get_real_tracer().start_as_current_span(name, **kwargs)

    def start_span(self, name: str, **kwargs: object) -> Span:
        return self._get_real_tracer().start_span(name, **kwargs)


def init_telemetry(settings: OpenTelemetrySettings) -> None:
    """
    Initialize OpenTelemetry tracing.

    Safe to call even if otel packages are not installed.
    Should be called once at application startup.

    Args:
        settings: OpenTelemetry configuration settings.
    """
    global _initialized, _tracer_provider

    if _initialized:
        logger.debug("Telemetry already initialized")
        return

    if not settings.enabled:
        logger.debug("Telemetry disabled")
        _initialized = True
        return

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    except ImportError:
        logger.warning(
            "OpenTelemetry packages not installed. "
            "Install with: pip install text-adventure[observability]"
        )
        _initialized = True
        return

    # Create resource with service name
    resource = Resource.create({"service.name": settings.service_name})

    # Create tracer provider
    provider = TracerProvider(resource=resource)

    # Always add console exporter for visibility
    console_exporter = ConsoleSpanExporter()
    provider.add_span_processor(BatchSpanProcessor(console_exporter))

    # Add OTLP exporter if endpoint configured
    if settings.endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

            otlp_exporter = OTLPSpanExporter(endpoint=settings.endpoint)
            provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
            logger.info(f"OTLP exporter configured: {settings.endpoint}")
        except ImportError:
            logger.warning("OTLP exporter not available, using console only")

    # Set as global tracer provider
    trace.set_tracer_provider(provider)
    _tracer_provider = provider
    _initialized = True

    logger.info(f"Telemetry initialized: service={settings.service_name}")


def get_tracer(name: str) -> Tracer:
    """
    Get a tracer for the given module name.

    Returns a lazy tracer that defers resolution until span creation.
    This allows modules to call get_tracer() at import time, before
    init_telemetry() is called.

    Args:
        name: Module name (typically __name__).

    Returns:
        A LazyTracer that resolves to real or no-op tracer when used.
    """
    return LazyTracer(name)


def shutdown_telemetry() -> None:
    """
    Shutdown the tracer provider, flushing any pending spans.

    Safe to call even if telemetry was never initialized.
    """
    global _initialized, _tracer_provider

    if _tracer_provider is not None:
        try:
            from opentelemetry.sdk.trace import TracerProvider

            if isinstance(_tracer_provider, TracerProvider):
                _tracer_provider.shutdown()
                logger.debug("Telemetry shutdown complete")
        except ImportError:
            pass

    _tracer_provider = None
    _initialized = False
