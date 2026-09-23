from __future__ import annotations

from contextlib import AbstractContextManager
from contextvars import ContextVar
from dataclasses import dataclass, field
from importlib.util import find_spec
from time import perf_counter
from typing import Any
from uuid import uuid4

from app.core.config import settings


_active_trace: ContextVar[dict[str, str] | None] = ContextVar("active_observability_trace", default=None)
_otel_configured = False
_otel_error: str | None = None


def _new_trace_id() -> str:
    return uuid4().hex


def _new_span_id() -> str:
    return uuid4().hex[:16]


@dataclass
class ObservabilitySpan(AbstractContextManager["ObservabilitySpan"]):
    name: str
    attributes: dict[str, Any] = field(default_factory=dict)
    trace_id: str | None = None
    span_id: str | None = None
    parent_span_id: str | None = None
    started_at: float | None = None
    ended_at: float | None = None
    error: str | None = None
    _token: Any = None
    _otel_cm: Any = None
    _otel_span: Any = None

    def __enter__(self) -> "ObservabilitySpan":
        parent = _active_trace.get()
        self.started_at = perf_counter()
        if settings.otel_enabled and configure_observability()["mode"] == "otel_configured":
            self._enter_otel_span()
        self.trace_id = self.trace_id or (parent or {}).get("trace_id") or _new_trace_id()
        self.parent_span_id = self.parent_span_id or (parent or {}).get("span_id")
        self.span_id = self.span_id or _new_span_id()
        self._token = _active_trace.set({"trace_id": self.trace_id, "span_id": self.span_id})
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool:
        self.ended_at = perf_counter()
        if exc is not None:
            self.error = str(exc)
            if self._otel_span is not None:
                try:
                    self._otel_span.record_exception(exc)
                    self._otel_span.set_attribute("error", True)
                except Exception:
                    pass
        if self._token is not None:
            _active_trace.reset(self._token)
        if self._otel_cm is not None:
            self._otel_cm.__exit__(exc_type, exc, traceback)
        return False

    @property
    def latency_ms(self) -> int | None:
        if self.started_at is None:
            return None
        end = self.ended_at or perf_counter()
        return round((end - self.started_at) * 1000)

    def _enter_otel_span(self) -> None:
        try:
            from opentelemetry import trace

            self._otel_cm = trace.get_tracer(settings.otel_service_name).start_as_current_span(
                self.name,
                attributes=_safe_otel_attributes(self.attributes),
            )
            self._otel_span = self._otel_cm.__enter__()
            span_context = self._otel_span.get_span_context()
            if span_context and span_context.is_valid:
                self.trace_id = f"{span_context.trace_id:032x}"
                self.span_id = f"{span_context.span_id:016x}"
        except Exception as exc:
            global _otel_error
            _otel_error = exc.__class__.__name__
            self._otel_cm = None
            self._otel_span = None


def start_span(name: str, *, attributes: dict[str, Any] | None = None) -> ObservabilitySpan:
    return ObservabilitySpan(name=name, attributes=attributes or {})


def current_trace_context() -> dict[str, str | None]:
    active = _active_trace.get() or {}
    if active.get("trace_id") or active.get("span_id"):
        return {
            "trace_id": active.get("trace_id"),
            "span_id": active.get("span_id"),
        }

    otel_context = _current_otel_trace_context()
    if otel_context.get("trace_id") or otel_context.get("span_id"):
        return otel_context

    return {
        "trace_id": None,
        "span_id": None,
    }


def _current_otel_trace_context() -> dict[str, str | None]:
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        context = span.get_span_context() if span is not None else None
        if context is not None and context.is_valid:
            return {
                "trace_id": f"{context.trace_id:032x}",
                "span_id": f"{context.span_id:016x}",
            }
    except Exception:
        pass

    return {"trace_id": None, "span_id": None}


def observability_status() -> dict[str, Any]:
    configured = configure_observability() if settings.otel_enabled else {"mode": "no_op"}
    return {
        "otelEnabled": settings.otel_enabled,
        "serviceName": settings.otel_service_name,
        "exporterConfigured": bool(settings.otel_exporter_otlp_endpoint),
        "sampleRate": settings.otel_sample_rate,
        "mode": configured["mode"],
        "error": _otel_error,
    }


def configure_observability() -> dict[str, Any]:
    global _otel_configured, _otel_error
    if not settings.otel_enabled:
        return {"mode": "no_op"}
    if _otel_configured:
        return {"mode": "otel_configured"}
    if not _otel_dependencies_available():
        _otel_error = "opentelemetry dependencies are not installed"
        return {"mode": "otel_unavailable"}

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

        resource = Resource.create({"service.name": settings.otel_service_name})
        provider = TracerProvider(
            resource=resource,
            sampler=TraceIdRatioBased(settings.otel_sample_rate),
        )
        exporter_kwargs: dict[str, Any] = {}
        if settings.otel_exporter_otlp_endpoint:
            exporter_kwargs["endpoint"] = settings.otel_exporter_otlp_endpoint
        headers = _parse_otel_headers(settings.otel_exporter_otlp_headers)
        if headers:
            exporter_kwargs["headers"] = headers
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(**exporter_kwargs)))
        trace.set_tracer_provider(provider)
        _otel_configured = True
        _otel_error = None
        return {"mode": "otel_configured"}
    except Exception as exc:
        _otel_error = exc.__class__.__name__
        return {"mode": "otel_unavailable"}


def instrument_fastapi_app(app: Any) -> dict[str, Any]:
    status = configure_observability()
    if status["mode"] != "otel_configured":
        return status
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)
        return {"mode": "otel_configured", "fastapiInstrumented": True}
    except Exception as exc:
        global _otel_error
        _otel_error = exc.__class__.__name__
        return {"mode": "otel_configured", "fastapiInstrumented": False}


def _otel_dependencies_available() -> bool:
    try:
        return all(
            find_spec(package) is not None
            for package in (
                "opentelemetry",
                "opentelemetry.sdk",
                "opentelemetry.exporter.otlp.proto.grpc.trace_exporter",
            )
        )
    except ModuleNotFoundError:
        return False


def _parse_otel_headers(value: str) -> dict[str, str]:
    headers: dict[str, str] = {}
    for item in value.split(","):
        if "=" not in item:
            continue
        key, raw_value = item.split("=", 1)
        key = key.strip()
        if key:
            headers[key] = raw_value.strip()
    return headers


def _safe_otel_attributes(attributes: dict[str, Any]) -> dict[str, str | int | float | bool]:
    safe: dict[str, str | int | float | bool] = {}
    for key, value in attributes.items():
        if isinstance(value, (str, int, float, bool)):
            safe[str(key)] = value
        elif value is not None:
            safe[str(key)] = str(value)[:500]
    return safe
