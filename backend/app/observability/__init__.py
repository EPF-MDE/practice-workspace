from __future__ import annotations

import logging
from collections.abc import Iterable, Iterator
from contextlib import AbstractContextManager, contextmanager, nullcontext
from dataclasses import dataclass
from typing import Any

import posthog
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.resources import Resource

LOGS_PATH = "/i/v1/logs"
SERVICE_LOGGERS = ("uvicorn", "uvicorn.error")


def check_settings(
    token: str, host: str, environment: str
) -> tuple[str, str, str] | None:
    token, host, environment = (
        token.strip(),
        host.strip().rstrip("/"),
        environment.strip(),
    )
    if not token:
        return None
    if not host:
        raise ValueError("WORKSPACE_POSTHOG_HOST missing")
    if not environment:
        raise ValueError("WORKSPACE_POSTHOG_ENVIRONMENT missing")
    return token, host, environment


@dataclass(frozen=True)
class _Wiring:
    client: posthog.Posthog
    logger_provider: LoggerProvider
    handler: LoggingHandler
    loggers: Iterable[logging.Logger]


class Signals:
    def __init__(self, wiring: _Wiring | None = None) -> None:
        self._wiring = wiring

    def request_context(
        self, distinct_id: str | None, **properties: Any
    ) -> AbstractContextManager[None]:
        if self._wiring is None:
            return nullcontext()
        return self._context(self._wiring.client, distinct_id, properties)

    @contextmanager
    def _context(
        self,
        client: posthog.Posthog,
        distinct_id: str | None,
        properties: dict[str, Any],
    ) -> Iterator[None]:
        with posthog.new_context(client=client):
            if distinct_id:
                posthog.identify_context(distinct_id)
            for name, value in properties.items():
                posthog.tag(name, value)
            yield

    def shutdown(self) -> None:
        wiring = self._wiring
        if wiring is None:
            return
        for logger in wiring.loggers:
            logger.removeHandler(wiring.handler)
        wiring.logger_provider.shutdown()
        wiring.client.shutdown()


def start(service_name: str, token: str, host: str, environment: str) -> Signals:
    settings = check_settings(token, host, environment)
    if settings is None:
        return Signals()
    token, host, environment = settings
    client = posthog.Posthog(
        token,
        host=host,
        enable_exception_autocapture=True,
        super_properties={"environment": environment, "service": service_name},
    )
    logger_provider = LoggerProvider(
        resource=Resource.create(
            {"service.name": service_name, "deployment.environment": environment}
        )
    )
    logger_provider.add_log_record_processor(
        BatchLogRecordProcessor(
            OTLPLogExporter(
                endpoint=host + LOGS_PATH, headers={"Authorization": f"Bearer {token}"}
            )
        )
    )
    handler = LoggingHandler(logger_provider=logger_provider)
    loggers = [logging.getLogger()] + [
        logger
        for logger in map(logging.getLogger, SERVICE_LOGGERS)
        if not logger.propagate
    ]
    for logger in loggers:
        logger.addHandler(handler)
    return Signals(_Wiring(client, logger_provider, handler, loggers))
