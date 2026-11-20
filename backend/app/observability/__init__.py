"""The app's own C3: its errors and logs, sent to the Instructor's PostHog project.

The Worked Examples' production signals (EPF-MDE/OceENS,
`src/oceens/production_signals.py`), for this app. Three settings, all or
none: `WORKSPACE_POSTHOG_PROJECT_TOKEN`, `WORKSPACE_POSTHOG_HOST` and
`WORKSPACE_POSTHOG_ENVIRONMENT` (`staging` or `production`). Without the token
nothing is wired and the app runs as before; with the token but not the other
two, the app refuses to start, so staging's errors never mix silently with
production's.

`start()` is called when the app starts (its lifespan), never at import:
uvicorn applies its own logging configuration after import, and would remove
the handler set here.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Iterator
from contextlib import AbstractContextManager, contextmanager, nullcontext
from typing import Any

import posthog
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.resources import Resource

# PostHog Logs' OTLP path, appended to the host.
LOGS_PATH = "/i/v1/logs"
# Under uvicorn these do not propagate to the root logger.
SERVICE_LOGGERS = ("uvicorn", "uvicorn.error")


def check_settings(
    token: str, host: str, environment: str
) -> tuple[str, str, str] | None:
    """`(token, host, environment)`, or None without a token.

    Raises ValueError, naming the setting, on a token without the other two.
    """
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


class Signals:
    """What `start()` wired, and how to unwire it. Off when `client` is None."""

    def __init__(
        self,
        client: posthog.Posthog | None = None,
        logger_provider: LoggerProvider | None = None,
        handler: LoggingHandler | None = None,
        loggers: Iterable[logging.Logger] = (),
    ) -> None:
        self._client = client
        self._logger_provider = logger_provider
        self._handler = handler
        self._loggers = loggers

    def request_context(
        self, distinct_id: str | None, **properties: Any
    ) -> AbstractContextManager[None]:
        """PostHog context of one request: an exception leaving it is captured
        under the signed-in Student's identity, then re-raised unchanged."""
        if self._client is None:
            return nullcontext()
        return self._context(distinct_id, properties)

    @contextmanager
    def _context(
        self, distinct_id: str | None, properties: dict[str, Any]
    ) -> Iterator[None]:
        with posthog.new_context(client=self._client):
            if distinct_id:
                posthog.identify_context(distinct_id)
            for name, value in properties.items():
                posthog.tag(name, value)
            yield

    def shutdown(self) -> None:
        if self._client is None:
            return
        # Set together with the client, by `start()`.
        assert self._handler is not None and self._logger_provider is not None
        for logger in self._loggers:
            logger.removeHandler(self._handler)
        self._logger_provider.shutdown()
        self._client.shutdown()


def start(service_name: str, token: str, host: str, environment: str) -> Signals:
    """Wire errors and logs to PostHog, if the three settings are set."""
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
    return Signals(client, logger_provider, handler, loggers)
