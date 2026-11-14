from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging_config import redact_text

logger = logging.getLogger(__name__)


class FieldError(BaseModel):
    field: str
    message: str


class Problem(BaseModel):
    type: str = "about:blank"
    title: str
    status: int
    code: str
    detail: str | None = None
    errors: list[FieldError] | None = None


class ProblemException(Exception):
    """Domain/HTTP error rendered as RFC 7807 application/problem+json."""

    def __init__(
        self,
        status_code: int,
        code: str,
        title: str,
        detail: str | None = None,
        errors: list[FieldError] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(detail or title)
        self.status_code = status_code
        self.code = code
        self.title = title
        self.detail = detail
        self.errors = errors
        self.headers = headers


def problem_response(
    status_code: int,
    code: str,
    title: str,
    detail: str | None = None,
    errors: list[FieldError] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    safe_detail = redact_text(detail) if detail else None
    body = Problem(
        type="about:blank",
        title=title,
        status=status_code,
        code=code,
        detail=safe_detail,
        errors=errors,
    ).model_dump(exclude_none=True)
    return JSONResponse(
        status_code=status_code,
        content=body,
        media_type="application/problem+json",
        headers=headers,
    )


_STATUS_TO_CODE: dict[int, tuple[str, str]] = {
    401: ("INVALID_CREDENTIALS", "Unauthorized"),
    403: ("FORBIDDEN", "Forbidden"),
    404: ("NOT_FOUND", "Not Found"),
    405: ("METHOD_NOT_ALLOWED", "Method Not Allowed"),
    409: ("CONFLICT", "Conflict"),
    413: ("BATCH_TOO_LARGE", "Payload Too Large"),
    415: ("UNSUPPORTED_MEDIA_TYPE", "Unsupported Media Type"),
    422: ("VALIDATION", "Validation Error"),
    429: ("RATE_LIMITED", "Too Many Requests"),
}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ProblemException)
    async def handle_problem_exception(
        _request: Request, exc: ProblemException
    ) -> JSONResponse:
        return problem_response(
            status_code=exc.status_code,
            code=exc.code,
            title=exc.title,
            detail=exc.detail,
            errors=exc.errors,
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        field_errors: list[FieldError] = []
        for err in exc.errors():
            loc_parts = [
                str(part)
                for part in err.get("loc", ())
                if part not in ("body", "query", "path")
            ]
            field_name = ".".join(loc_parts) if loc_parts else "request"
            field_errors.append(
                FieldError(field=field_name, message=str(err.get("msg", "Invalid value")))
            )
        return problem_response(
            status_code=422,
            code="VALIDATION",
            title="Validation Error",
            detail="Request validation failed",
            errors=field_errors,
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(
        _request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        code, title = _STATUS_TO_CODE.get(
            exc.status_code, ("HTTP_ERROR", "Request Error")
        )
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        headers: dict[str, str] | None = None
        if exc.headers:
            headers = dict(exc.headers)
        return problem_response(
            status_code=exc.status_code,
            code=code,
            title=title,
            detail=detail,
            headers=headers,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.exception(
            "Unhandled internal error on %s %s",
            request.method,
            request.url.path,
            exc_info=exc,
        )
        return problem_response(
            status_code=500,
            code="INTERNAL_ERROR",
            title="Internal Server Error",
            detail="An unexpected internal error occurred",
        )


class MessageOnly(BaseModel):
    status: str = Field(default="ok")


def problem_dict(status_code: int, code: str, title: str, detail: str) -> dict[str, Any]:
    return Problem(status=status_code, code=code, title=title, detail=detail).model_dump(
        exclude_none=True
    )
