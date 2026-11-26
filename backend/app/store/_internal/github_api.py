from __future__ import annotations

from typing import Any

import httpx

from app.store._internal.model import StoreUnavailable

PER_PAGE = 100


class GitHubApi:
    def __init__(self, http: httpx.Client, repository: str):
        self.http = http
        self.repository = repository

    def call(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        try:
            response = self.http.request(method, url, **kwargs)
        except httpx.HTTPError as error:
            raise StoreUnavailable(f"GitHub did not answer: {error}") from error
        if response.is_error:
            raise StoreUnavailable(
                f"GitHub answered {response.status_code} to {method} {url}"
            )
        return response

    def all_pages(self, url: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        response = self.call("GET", url, params={**params, "per_page": PER_PAGE})
        while True:
            items += response.json()
            following = response.links.get("next", {}).get("url")
            if not following:
                return items
            response = self.call("GET", following)
