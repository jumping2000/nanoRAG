from __future__ import annotations

import contextvars
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from config import Settings

_HANDLER_NAME = "nanorag-observability"
_request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")
_environment_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "environment",
    default="development",
)
_trace_var: contextvars.ContextVar[TraceCollector | None] = contextvars.ContextVar(
    "trace_collector",
    default=None,
)


def _serialize(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {str(key): _serialize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_serialize(item) for item in value]
    return str(value)


@dataclass(slots=True)
class TraceCollector:
    request_id: str
    environment: str
    started_at: float = field(default_factory=time.perf_counter)
    events: list[dict[str, Any]] = field(default_factory=list)

    def add(self, component: str, action: str, details: dict[str, Any]) -> None:
        self.events.append(
            {
                "at": datetime.now(UTC).isoformat(),
                "component": component,
                "action": action,
                "details": _serialize(details),
            }
        )

    def snapshot(self) -> dict[str, Any]:
        return {
            "requestId": self.request_id,
            "environment": self.environment,
            "elapsedMs": round((time.perf_counter() - self.started_at) * 1000, 2),
            "events": list(self.events),
        }


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id_var.get()
        record.environment = _environment_var.get()
        return True


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", _request_id_var.get()),
            "environment": getattr(record, "environment", _environment_var.get()),
        }
        event_name = getattr(record, "event_name", None)
        if event_name:
            payload["event"] = event_name
        details = getattr(record, "details", None)
        if details:
            payload["details"] = _serialize(details)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(settings: Settings) -> None:
    if settings.is_debug:
        level = logging.DEBUG
    elif settings.is_development:
        level = logging.INFO
    else:
        level = logging.WARNING

    handler = logging.StreamHandler()
    handler.set_name(_HANDLER_NAME)
    handler.setFormatter(JsonLogFormatter())
    handler.addFilter(RequestContextFilter())
    logging.basicConfig(level=level, handlers=[handler], force=True)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)


def bind_request_context(
    request_id: str,
    environment: str,
    trace_collector: TraceCollector | None = None,
) -> tuple[contextvars.Token[str], contextvars.Token[str], contextvars.Token[TraceCollector | None]]:
    request_token = _request_id_var.set(request_id)
    environment_token = _environment_var.set(environment)
    trace_token = _trace_var.set(trace_collector)
    return request_token, environment_token, trace_token


def start_request_context(
    request_id: str,
    settings: Settings,
) -> tuple[
    tuple[contextvars.Token[str], contextvars.Token[str], contextvars.Token[TraceCollector | None]],
    TraceCollector | None,
]:
    trace_collector = None
    if settings.enable_trace_details:
        trace_collector = TraceCollector(request_id=request_id, environment=settings.environment)
    tokens = bind_request_context(
        request_id=request_id,
        environment=settings.environment,
        trace_collector=trace_collector,
    )
    return tokens, trace_collector


def reset_request_context(
    tokens: tuple[
        contextvars.Token[str],
        contextvars.Token[str],
        contextvars.Token[TraceCollector | None],
    ],
) -> None:
    request_token, environment_token, trace_token = tokens
    _trace_var.reset(trace_token)
    _environment_var.reset(environment_token)
    _request_id_var.reset(request_token)


def clear_request_context() -> None:
    _trace_var.set(None)
    _environment_var.set("development")
    _request_id_var.set("-")


def current_request_id() -> str:
    return _request_id_var.get()


def current_trace() -> TraceCollector | None:
    return _trace_var.get()


def observe(
    logger: logging.Logger,
    level: int,
    component: str,
    action: str,
    **details: Any,
) -> None:
    clean_details = {
        key: _serialize(value)
        for key, value in details.items()
        if value is not None
    }
    event_name = f"{component}.{action}"
    logger.log(
        level,
        event_name,
        extra={"event_name": event_name, "details": clean_details},
    )

    trace_collector = current_trace()
    if trace_collector is not None:
        trace_collector.add(component=component, action=action, details=clean_details)