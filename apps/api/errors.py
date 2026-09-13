"""Stripe-style structured error envelope (spec §9.3, Task 25)."""

from fastapi.responses import JSONResponse


def error_response(
    error_type: str,
    code: str,
    message: str,
    param: str | None,
    request_id: str,
    status_code: int,
) -> JSONResponse:
    """Build a structured error response body."""
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "type": error_type,
                "code": code,
                "message": message,
                "param": param,
                "request_id": request_id,
                "doc_url": None,
            }
        },
    )
