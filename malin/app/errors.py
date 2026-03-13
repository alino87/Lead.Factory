"""
MALIN Error Handling — SPEC §6 (Graceful Degradation).

No raw 500s. Every error returns structured JSON:
  {"error_code": "...", "detail": "...", "needs_review": bool}

Standard Error Codes (SPEC §6.1):
  OCR_MISSING, LLM_PARSE, SPAN_MISMATCH, LLM_RATE_LIMIT,
  LLM_AUTH, LLM_TIMEOUT, EXECUTION_FAILED, ILLEGAL_STATE
"""

import logging

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("malin.errors")


# ── Base Error ────────────────────────────────────────────────────────────────

class MalinError(Exception):
    def __init__(
        self,
        error_code: str,
        detail: str,
        status_code: int = 400,
        needs_review: bool = False,
    ):
        self.error_code = error_code
        self.detail = detail
        self.status_code = status_code
        self.needs_review = needs_review
        super().__init__(detail)


# ── SPEC §5.2 — State Machine ────────────────────────────────────────────────

class IllegalStateError(MalinError):
    """ILLEGAL_STATE — action not allowed in current state."""
    def __init__(self, current_status: str, attempted_action: str):
        super().__init__(
            error_code="ILLEGAL_STATE",
            detail=f"Cannot {attempted_action}: draft is in status '{current_status}'",
            status_code=409,
            needs_review=True,
        )


# ── SPEC §6.1 — Standard Error Codes ─────────────────────────────────────────

class OcrMissingError(MalinError):
    def __init__(self, document_id: str):
        super().__init__(
            error_code="OCR_MISSING",
            detail=f"No OCR spans for document '{document_id}'. Run OCR first.",
            status_code=422,
            needs_review=True,
        )


class LlmParseError(MalinError):
    def __init__(self, detail: str = "LLM output could not be parsed as valid JSON"):
        super().__init__(error_code="LLM_PARSE", detail=detail, status_code=422, needs_review=True)


class SpanMismatchError(MalinError):
    def __init__(self, span_id: str):
        super().__init__(
            error_code="SPAN_MISMATCH",
            detail=f"Evidence span_id '{span_id}' not found in ocr_spans",
            status_code=422,
            needs_review=True,
        )


class LlmRateLimitError(MalinError):
    def __init__(self):
        super().__init__(error_code="LLM_RATE_LIMIT", detail="LLM rate limit reached.", status_code=429, needs_review=True)


class LlmAuthError(MalinError):
    def __init__(self):
        super().__init__(error_code="LLM_AUTH", detail="LLM API authentication failed.", status_code=502, needs_review=True)


class LlmTimeoutError(MalinError):
    def __init__(self):
        super().__init__(error_code="LLM_TIMEOUT", detail="LLM request timed out.", status_code=504, needs_review=True)


class ExecutionFailedError(MalinError):
    def __init__(self, detail: str):
        super().__init__(error_code="EXECUTION_FAILED", detail=detail, status_code=500, needs_review=True)


# ── Auth / Access ─────────────────────────────────────────────────────────────

class AuthError(MalinError):
    def __init__(self, detail: str = "Invalid or missing API key"):
        super().__init__(error_code="AUTH_ERROR", detail=detail, status_code=401)


class TenantSuspendedError(MalinError):
    """SPEC §7.7 — plan gating: 402 if tenant inactive/suspended."""
    def __init__(self):
        super().__init__(error_code="TENANT_SUSPENDED", detail="Tenant is suspended.", status_code=402)


class NotFoundError(MalinError):
    def __init__(self, entity: str, entity_id: str):
        super().__init__(error_code="NOT_FOUND", detail=f"{entity} '{entity_id}' not found", status_code=404)


class StorageError(MalinError):
    def __init__(self, detail: str):
        super().__init__(error_code="STORAGE_ERROR", detail=detail, status_code=502, needs_review=True)


class FileTooLargeError(MalinError):
    def __init__(self, max_mb: int = 20):
        super().__init__(error_code="FILE_TOO_LARGE", detail=f"Max file size: {max_mb} MB", status_code=413)


class RateLimitedError(MalinError):
    """SPEC §11 — basic rate limiting."""
    def __init__(self):
        super().__init__(error_code="RATE_LIMITED", detail="Too many requests.", status_code=429)


# ── Handlers ──────────────────────────────────────────────────────────────────

def malin_error_handler(_request: Request, exc: MalinError) -> JSONResponse:
    # PII safe: only IDs + error codes in logs, never document content (SPEC §11)
    logger.warning(f"[{exc.error_code}] {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"error_code": exc.error_code, "detail": exc.detail, "needs_review": exc.needs_review},
    )


def generic_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception")
    return JSONResponse(
        status_code=500,
        content={"error_code": "INTERNAL_ERROR", "detail": "An unexpected error occurred", "needs_review": True},
    )
