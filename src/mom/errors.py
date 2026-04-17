"""Exception classes used across the package."""


class MomError(Exception):
    """Base for all mom errors."""


class UnsupportedCharError(MomError):
    def __init__(self, char: str) -> None:
        self.char = char
        super().__init__(
            f"Character {char!r} not supported. Allowed: printable ASCII (0x20-0x7E)."
        )


class FitError(MomError):
    def __init__(self, required: int, available: int, year: int) -> None:
        self.required = required
        self.available = available
        self.year = year
        max_chars = max(0, (available + 1) // 4)
        super().__init__(
            f"Doesn't fit. Required {required} cols, available {available} for year {year}. "
            f"Max text: ~{max_chars} chars. Try a different --year or shorten the text."
        )


class AuthError(MomError):
    def __init__(self, kind: str, message: str) -> None:
        self.kind = kind
        super().__init__(message)


class NotOurRepoError(MomError):
    def __init__(self, repo_name: str) -> None:
        self.repo_name = repo_name
        super().__init__(
            f"Repo '{repo_name}' isn't managed by mom (no .mom-state.json). "
            f"Refusing to touch it. Pick a different --repo."
        )


class NetworkError(MomError):
    pass
