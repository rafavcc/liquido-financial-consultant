from collections.abc import Callable
from datetime import date
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response

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

    static_root = app.state.container.static_dir
    if static_root is not None and static_root.is_dir():
        _mount_spa(app, static_root.resolve())
    return app


def _mount_spa(app: FastAPI, root: Path) -> None:
    index = root / "index.html"

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str) -> Response:
        if full_path == "api" or full_path.startswith("api/"):
            return JSONResponse(status_code=404, content={"detail": "Não encontrado"})
        candidate = (root / full_path).resolve()
        if candidate.is_file() and candidate.is_relative_to(root):
            # arquivos com hash em /assets nunca mudam; sw.js e index.html precisam ser revalidados
            if candidate.relative_to(root).parts[0] == "assets":
                cache = "public, max-age=31536000, immutable"
            else:
                cache = "no-cache"
            return FileResponse(candidate, headers={"Cache-Control": cache})
        return FileResponse(index, headers={"Cache-Control": "no-cache"})


app = create_app()
