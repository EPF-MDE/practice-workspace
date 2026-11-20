"""The token each repository is read with: the Student Connector's installation on
it, asked once; a repository it is not installed on is asked again after a while."""

from collections.abc import Callable

from app.repository_reading.github import INSTALLED_TTL, tokens_per_repository


class Installations:
    """The App's installations, by repository, counting every question."""

    def __init__(self, tokens: dict[str, str]) -> None:
        self.tokens = tokens
        self.asked: list[str] = []

    def __call__(self, repository: str) -> Callable[[], str] | None:
        self.asked.append(repository)
        token = self.tokens.get(repository)
        return None if token is None else lambda: token


def test_a_repository_the_app_is_not_installed_on_is_asked_again_after_a_while() -> (
    None
):
    now = [0.0]
    installations = Installations({})
    token = tokens_per_repository(installations, lambda: "default", lambda: now[0])

    assert token("Ada/Bakery") == "default"
    now[0] = INSTALLED_TTL
    assert token("ada/bakery") == "default"
    assert installations.asked == ["Ada/Bakery"]

    now[0] = INSTALLED_TTL + 1
    installations.tokens["ada/bakery"] = "ada's"
    assert token("ada/bakery") == "ada's"
    assert installations.asked == ["Ada/Bakery", "ada/bakery"]


def test_a_repository_the_app_is_installed_on_is_asked_once() -> None:
    now = [0.0]
    installations = Installations({"ada/bakery": "ada's"})
    token = tokens_per_repository(installations, lambda: "default", lambda: now[0])

    assert token("ada/bakery") == "ada's"
    now[0] = 10 * INSTALLED_TTL
    assert token("ada/bakery") == "ada's"
    assert installations.asked == ["ada/bakery"]
