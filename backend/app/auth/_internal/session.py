from __future__ import annotations

import secrets
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Literal

import itsdangerous
from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware
from starlette.types import ASGIApp

_SESSION_IDLE_LIMIT = timedelta(days=60)


class _ClockSigner(itsdangerous.TimestampSigner):
    def __init__(self, secret: str, clock: Callable[[], datetime]) -> None:
        super().__init__(secret)
        self._clock = clock

    def get_timestamp(self) -> int:
        return int(self._clock().timestamp())


class _ClockSessionMiddleware(SessionMiddleware):
    def __init__(
        self,
        app: ASGIApp,
        /,
        secret_key: str,
        clock: Callable[[], datetime],
        session_cookie: str,
        max_age: int,
        same_site: Literal["lax", "strict", "none"],
        https_only: bool,
    ) -> None:
        super().__init__(
            app,
            secret_key=secret_key,
            session_cookie=session_cookie,
            max_age=max_age,
            same_site=same_site,
            https_only=https_only,
        )
        self.signer = _ClockSigner(secret_key, clock)


def add_session(
    app: FastAPI, secret: str, https_only: bool, clock: Callable[[], datetime]
) -> None:
    app.add_middleware(
        _ClockSessionMiddleware,
        secret_key=secret or secrets.token_urlsafe(32),
        clock=clock,
        session_cookie="cws_session",
        max_age=int(_SESSION_IDLE_LIMIT.total_seconds()),
        same_site="lax",
        https_only=https_only,
    )
