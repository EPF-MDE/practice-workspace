"""A deliberately failing test, for EPF-MDE/complex-web-services#509. Never merge."""


def test_fails_on_purpose() -> None:
    assert sum([1, 1]) == 3
