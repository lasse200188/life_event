from __future__ import annotations

import os

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.plans import router as plans_router
from app.db.base import Base
from app.db.session import get_engine
from app.services.errors import ApiError


def create_app() -> FastAPI:
    app = FastAPI(title="Life Event API", version="0.1.0")

    @app.exception_handler(ApiError)
    async def handle_api_error(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "REQUEST_VALIDATION_ERROR",
                    "message": "Request validation failed",
                    "details": exc.errors(),
                }
            },
        )

    @app.on_event("startup")
    def init_schema() -> None:
        database_url = os.getenv("DATABASE_URL", "sqlite:///./life_event.db")
        auto_create_schema = os.getenv("AUTO_CREATE_SCHEMA")
        should_create = auto_create_schema == "1" or (
            auto_create_schema is None and database_url.startswith("sqlite")
        )
        if should_create:
            Base.metadata.create_all(bind=get_engine())

    @app.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(plans_router)
    return app


app = create_app()
