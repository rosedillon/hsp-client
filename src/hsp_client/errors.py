"""Exceptions raised by the HSP client."""

from __future__ import annotations


class HspError(Exception):
    """Base class for every error this package raises."""


class MissingCredentialsError(HspError):
    """No NRDP username/password could be found."""

    def __init__(self) -> None:
        super().__init__(
            "No National Rail Data Portal credentials found. Set the "
            "NRDP_USERNAME and NRDP_PASSWORD environment variables, or pass "
            "username= and password= explicitly. Register at "
            "https://opendata.nationalrail.co.uk and tick 'HSP' under "
            "Subscription type."
        )


class AuthenticationError(HspError):
    """HSP rejected the credentials, or the account lacks HSP access."""

    def __init__(self, status: int) -> None:
        super().__init__(
            f"HSP rejected the credentials (HTTP {status}). Check the username and "
            "password, and confirm the account has 'HSP' ticked under Subscription "
            "type at https://opendata.nationalrail.co.uk. An NRDP account without "
            "that subscription works for the other feeds but not for HSP."
        )


class HspRequestError(HspError):
    """HSP returned an unsuccessful HTTP status."""

    def __init__(self, status: int, body: str) -> None:
        self.status = status
        self.body = body
        detail = body.strip()[:500] or "(empty response body)"
        super().__init__(f"HSP request failed with HTTP {status}: {detail}")


class InvalidRequestError(HspError, ValueError):
    """A query argument HSP would reject, caught before sending."""
