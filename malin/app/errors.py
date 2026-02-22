"""
Structured error handling – no raw 500s.

Every error returns:
  {"error_code": "...", "detail": "...", "needs_review": bool}
"""

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse


class MalinError(Exception):
    """Base error with structured error_code."""
    def __init__(self, error_code: str, detail: str, status_code: int = 400, needs_review: bool = False):
        self.error_code = error_code
        self.detail = detail
        self.status_code = status_code
        self.needs_review = needs_review
        super().__init__(detail)


class IllegalStateError(MalinError):
    """Draft is Law: action not allowed in current state."""
    def __init__(self, current_status: str, attempted_action: str):
        super().__init__(
            error_code="ILLEGAL_STATE_TRANSITION",
            detail=f"Cannot {attempted_action} draft in status '{current_status}'",
            status_code=409,
            needs_review=True,
        )


class NotFoundError(MalinError):
    def __init__(self, entity: str, entity_id: str):
        super().__init__(
            error_code="NOT_FOUND",
            detail=f"{entity} '{entity_id}' not found",
            status_code=404,
        )


class AuthError(MalinError):
    def __init__(self, detail: str = "Invalid or missing API key"):
        super().__init__(
            error_code="AUTH_ERROR",
            detail=detail,
            status_code=401,
        )


class StorageError(MalinError):
    def __init__(self, detail: str):
        super().__init__(
            error_code="STORAGE_ERROR",
            detail=detail,
            status_code=502,
            needs_review=True,
        )


def malin_error_handler(_request: Request, exc: MalinError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error_code": exc.error_code,
            "detail": exc.detail,
            "needs_review": exc.needs_review,
        },
    )


def generic_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={
            "error_code": "INTERNAL_ERROR",
            "detail": "An unexpected error occurred",
            "needs_review": True,
        },
    )
