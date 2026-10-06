"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from pokequant import __version__
from pokequant.api.errors import install_exception_handlers
from pokequant.api.routers import api_router
from pokequant.core.config import get_settings
from pokequant.core.logging import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)

    app = FastAPI(
        title="PokeQuant API",
        version=__version__,
        summary="Quantitative research & forecasting for alternative assets (Phase 1).",
        default_response_class=ORJSONResponse,
    )

    if settings.cors_origins_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins_list,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Phase 4: middleware stack (logging, rate limit, compression, security headers).
    from pokequant.api.middleware import install_middleware
    install_middleware(app)

    install_exception_handlers(app)
    app.include_router(api_router)
    return app


app = create_app()
