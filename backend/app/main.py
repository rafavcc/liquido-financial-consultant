from collections.abc import Callable
from datetime import date
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
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
    spa = _spa_responder(static_root.resolve()) if static_root is not None and static_root.is_dir() else None

    @app.exception_handler(StarletteHTTPException)
    async def _http_handler(request: Request, exc: StarletteHTTPException) -> Response:
        if exc.status_code != 404 or exc.detail != "Not Found":
            return await http_exception_handler(request, exc)  # 404 levantado por uma rota, 405 etc.
        path = request.url.path
        is_api = path == "/api" or path.startswith("/api/")
        if exc.status_code == 404 and spa is not None and not is_api and request.method in ("GET", "HEAD"):
            return spa(path.lstrip("/"))
        return _not_found()

    return app


def _not_found() -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": "Não encontrado"})


def _spa_responder(root: Path) -> Callable[[str], Response]:
    index = root / "index.html"

    def respond(full_path: str) -> Response:
        if "\x00" in full_path:
            return _not_found()
        try:
            candidate = (root / full_path).resolve()
            is_file = candidate.is_file() and candidate.is_relative_to(root)
        except (OSError, ValueError):
            return _not_found()
        if is_file:
            # arquivos com hash em /assets nunca mudam; sw.js e index.html precisam ser revalidados
            if candidate.relative_to(root).parts[0] == "assets":
                cache = "public, max-age=31536000, immutable"
            else:
                cache = "no-cache"
            return FileResponse(candidate, headers={"Cache-Control": cache})
        if full_path.startswith("assets/"):
            # chunk antigo após um deploy: falha limpa em vez de devolver HTML como JS
            return _not_found()
        return FileResponse(index, headers={"Cache-Control": "no-cache"})

    return respond


app = create_app()
