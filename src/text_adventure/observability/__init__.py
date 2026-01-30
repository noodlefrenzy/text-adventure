"""
observability/__init__.py

PURPOSE: OpenTelemetry observability module for tracing.
DEPENDENCIES: opentelemetry-api, opentelemetry-sdk (optional)

ARCHITECTURE NOTES:
This module provides tracing capabilities that are opt-in:
- Works without otel packages installed (no-op mode)
- Console output by default when enabled
- OTLP export when endpoint is configured
"""

from text_adventure.observability.telemetry import get_tracer, init_telemetry

__all__ = ["init_telemetry", "get_tracer"]
