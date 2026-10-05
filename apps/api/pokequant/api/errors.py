"""Map application errors to RFC-7807-ish JSON responses."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from pokequant.core.errors import AppError
from pokequant.core.logging import get_logger

log = get_logger(__name__)


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        if exc.status_code >= 500:
            log.error("app_error", code=exc.code, message=exc.message, path=request.url.path)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "type": f"about:blank#{exc.code}",
                "title": exc.code,
                "status": exc.status_code,
                "detail": exc.message,
                "instance": request.url.path,
                **({"errors": exc.details} if exc.details else {}),
            },
        )
