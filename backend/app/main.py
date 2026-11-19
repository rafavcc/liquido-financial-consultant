from collections.abc import Callable
from datetime import date
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api import format_errors, market, products, settings, simulate
from app.data.market import MarketFetchers
from app.deps import build_container


def create_app(
    db_path: Path | None = None,
    fetchers: MarketFetchers | None = None,
    static_dir: Path | None = None,
    today_fn: Callable[[], date] = date.today,
) -> FastAPI:
    app = FastAPI(title="Liquido")
    app.state.container = build_container(db_path, fetchers, static_dir, today_fn)

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": format_errors(list(exc.errors()))})

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    for module in (simulate, products, settings, market):
        app.include_router(module.router, prefix="/api")
    return app


app = create_app()
