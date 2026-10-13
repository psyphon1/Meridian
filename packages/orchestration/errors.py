"""Typed domain errors for the orchestration package."""

from packages.github.errors import MeridianError

#: Machine-readable error code the API maps to HTTP 400 (ADR-006 D7).
WEBHOOK_PAYLOAD_INVALID = "webhook.payload_invalid"


class OrchestrationError(MeridianError):
    """Base class for orchestration-layer failures."""


class WebhookPayloadError(OrchestrationError):
    """The webhook body is not valid JSON or does not match its event's schema.

    The API layer maps this to ``400`` with code ``webhook.payload_invalid``
    (ADR-006 D7). ``detail`` is a short, safe description (no payload content).
    """

    code: str = WEBHOOK_PAYLOAD_INVALID

    def __init__(self, event: str, detail: str, delivery_id: str = "") -> None:
        super().__init__(f"invalid {event!r} webhook payload: {detail}")
        self.event = event
        self.detail = detail
        self.delivery_id = delivery_id
