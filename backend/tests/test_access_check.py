from __future__ import annotations

import base64
from typing import Any

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.evidence_panel import AppAccessCheck, Readability
from app.roster import Repository


@pytest.fixture(scope="module")
def key() -> str:
    pem = rsa.generate_private_key(public_exponent=65537, key_size=2048).private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    return base64.b64encode(pem).decode()


def github(
    answers: dict[str, tuple[int, dict[str, Any]]], seen: list[httpx.Request]
) -> httpx.Client:
    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        status, body = answers.get(request.url.path, (404, {"message": "Not Found"}))
        return httpx.Response(status, json=body)

    return httpx.Client(
        base_url="https://api.github.com", transport=httpx.MockTransport(handle)
    )


def test_a_repository_the_app_is_installed_on_is_readable_asked_as_the_app(
    key: str,
) -> None:
    seen: list[httpx.Request] = []
    check = AppAccessCheck(
        "123", key, github({"/repos/ada/secret/installation": (200, {"id": 9})}, seen)
    )

    assert check.can_read(Repository("ada/secret")) == Readability.READABLE
    assert seen[0].headers["Authorization"].startswith("Bearer ey")
    assert all(r.method == "GET" for r in seen)
    assert not any("/contents" in r.url.path for r in seen)


def test_a_public_repository_is_readable_without_the_app(key: str) -> None:
    seen: list[httpx.Request] = []
    check = AppAccessCheck(
        "123", key, github({"/repos/ada/bakery": (200, {"private": False})}, seen)
    )

    assert check.can_read(Repository("ada/bakery")) == Readability.READABLE


def test_a_private_repository_without_the_app_is_not_readable(key: str) -> None:
    check = AppAccessCheck("123", key, github({}, []))

    assert check.can_read(Repository("ada/secret")) == Readability.NOT_READABLE


def test_github_failing_means_it_could_not_check(key: str) -> None:
    check = AppAccessCheck(
        "123", key, github({"/repos/ada/secret/installation": (502, {})}, [])
    )

    assert check.can_read(Repository("ada/secret")) == Readability.NOT_CHECKED


def test_an_app_without_credentials_could_not_check() -> None:
    check = AppAccessCheck("", "", github({}, []))

    assert check.can_read(Repository("ada/secret")) == Readability.NOT_CHECKED


def test_an_answer_is_kept_a_minute(key: str) -> None:
    seen: list[httpx.Request] = []
    now = [0.0]
    check = AppAccessCheck("123", key, github({}, seen), clock=lambda: now[0])

    check.can_read(Repository("ada/secret"))
    check.can_read(Repository("ada/secret"))
    asked = len(seen)
    now[0] = 61
    check.can_read(Repository("ada/secret"))

    assert asked == 2
    assert len(seen) == 4
