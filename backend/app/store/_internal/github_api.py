from __future__ import annotations

from typing import Any

import httpx

from app.store._internal.model import StoreUnavailable

PER_PAGE = 100


class GitHubApi:
    def __init__(self, http: httpx.Client, repository: str):
        self._http = http
        self.repository = repository

    def call(
        self,
        method: str,
        path: str,
        handled: frozenset[int] = frozenset(),
        **kwargs: Any,
    ) -> httpx.Response:
        return self._request(
            method, f"/repos/{self.repository}/{path}", handled, **kwargs
        )

    def all_pages(self, path: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        response = self.call("GET", path, params={**params, "per_page": PER_PAGE})
        while True:
            items += response.json()
            following = response.links.get("next", {}).get("url")
            if not following:
                return items
            response = self._request("GET", following, frozenset())

    def _request(
        self, method: str, url: str, handled: frozenset[int], **kwargs: Any
    ) -> httpx.Response:
        try:
            response = self._http.request(method, url, **kwargs)
        except httpx.HTTPError as error:
            raise StoreUnavailable(f"GitHub did not answer: {error}") from error
        if response.is_error and response.status_code not in handled:
            raise StoreUnavailable(
                f"GitHub answered {response.status_code} to {method} {url}"
            )
        return response
