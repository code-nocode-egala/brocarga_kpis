"""Errors raised by the Bubble integration.

`apps.api.exception_handler` maps these onto HTTP responses, so views never
catch transport errors themselves.
"""

from __future__ import annotations


class BubbleError(Exception):
    """Base class for every failure originating in the Bubble integration."""

    http_status = 502
    detail = "The Bubble data source is unavailable."


class BubbleAuthError(BubbleError):
    """The API token was rejected. Not retryable -- surfaces as 502, alerts loudly."""

    http_status = 502
    detail = "The backend could not authenticate against Bubble."


class BubbleRateLimited(BubbleError):
    """Bubble returned 429. Retried with backoff before it ever reaches a view."""

    http_status = 503
    detail = "The Bubble data source is rate limiting requests. Try again shortly."


class BubbleUnavailable(BubbleError):
    """Timeout, connection failure, or a 5xx that survived every retry."""

    http_status = 503
    detail = "The Bubble data source did not respond. Try again shortly."


class BubbleMappingError(BubbleError):
    """A Bubble row did not match the expected shape.

    Raised only when a row cannot be salvaged; the loader logs and skips
    individual bad rows rather than failing a whole sync.
    """

    http_status = 502
    detail = "Unexpected data shape received from Bubble."
