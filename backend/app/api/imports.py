from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.data.imports_repo import ImportBatch, ImportFailure, ImportItem
from app.deps import Container, get_container
from app.domain.products.base import ProductData
from app.imports.service import ImportService, UploadedFile

router = APIRouter()

_NAO_CONFIGURADA = "Importação não configurada (defina LLM_BASE_URL e CASA_LLM_MODEL)"


class ImportItemView(BaseModel):
    id: str
    nome_arquivo: str
    print_id: str
    status: str
    erro: str | None
    criados: int
    renovados: int
    ignorados: int
    falhas: int


class ImportBatchView(BaseModel):
    id: str
    criado_em: str
    pendentes: int
    itens: list[ImportItemView]


class ImportFailureView(BaseModel):
    id: str
    item_id: str
    print_id: str | None
    nome_arquivo: str | None
    erros: list[str]
    parcial: dict
    status: str


class ImportCreated(BaseModel):
    lote: ImportBatchView
    recusados: list[str]


class ImportStatus(BaseModel):
    configurado: bool
    alcancavel: bool | None
    modelo: str | None


def _item_view(i: ImportItem) -> ImportItemView:
    return ImportItemView(**i.model_dump(include=set(ImportItemView.model_fields)))


def _batch_view(b: ImportBatch) -> ImportBatchView:
    return ImportBatchView(
        id=b.id,
        criado_em=b.criado_em,
        pendentes=sum(1 for i in b.itens if i.status in ("NA_FILA", "LENDO")),
        itens=[_item_view(i) for i in b.itens],
    )


def _service(c: Container) -> ImportService:
    if c.imports is None or c.llm is None:
        raise HTTPException(503, _NAO_CONFIGURADA)
    return c.imports


@router.get("/imports/status")
def status(c: Container = Depends(get_container)) -> ImportStatus:
    if c.llm is None:
        return ImportStatus(configurado=False, alcancavel=None, modelo=None)
    return ImportStatus(configurado=True, alcancavel=c.llm.ping(), modelo=c.llm_model)


@router.post("/imports", status_code=201)
async def create_import(arquivos: list[UploadFile], c: Container = Depends(get_container)) -> ImportCreated:
    service = _service(c)
    files = [UploadedFile(f.filename or "sem-nome", await f.read()) for f in arquivos]
    try:
        batch_id, recusas = service.enqueue(files)
    except ValueError as exc:
        raise HTTPException(422, exc.args[0] if exc.args else "Nenhum arquivo válido") from exc
    c.import_wake.set()
    with c.lock:
        batch = c.imports._repo.get_batch(batch_id)
    return ImportCreated(lote=_batch_view(batch), recusados=recusas)


@router.get("/imports")
def list_imports(c: Container = Depends(get_container)) -> list[ImportBatchView]:
    with c.lock:
        return [_batch_view(b) for b in c.imports._repo.list_batches()]


@router.get("/imports/failures")
def list_failures(status: str | None = "ABERTA", c: Container = Depends(get_container)) -> list[ImportFailureView]:
    with c.lock:
        repo = c.imports._repo
        out = []
        for f in repo.list_failures(status):
            item = repo.get_item(f.item_id)
            out.append(_failure_view(f, item.nome_arquivo if item else None))
        return out


def _failure_view(f: ImportFailure, nome: str | None) -> ImportFailureView:
    return ImportFailureView(
        id=f.id, item_id=f.item_id, print_id=f.print_id, nome_arquivo=nome,
        erros=f.erros, parcial=f.parcial, status=f.status,
    )


@router.post("/imports/failures/{failure_id}/resolve", status_code=201)
def resolve_failure(failure_id: str, data: ProductData, c: Container = Depends(get_container)) -> ProductData:
    try:
        return c.imports.resolve_failure(failure_id, data)
    except KeyError:
        raise HTTPException(404, "Falha não encontrada")
    except ValueError as exc:
        arg = exc.args[0] if exc.args else "Conflito"
        raise HTTPException(422 if isinstance(arg, list) else 409, arg) from exc


@router.post("/imports/failures/{failure_id}/discard", status_code=204)
def discard_failure(failure_id: str, c: Container = Depends(get_container)) -> Response:
    try:
        c.imports.discard_failure(failure_id)
    except KeyError:
        raise HTTPException(404, "Falha não encontrada")
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return Response(status_code=204)


@router.post("/imports/items/{item_id}/retry")
def retry_item(item_id: str, c: Container = Depends(get_container)) -> ImportItemView:
    try:
        c.imports.retry_item(item_id)
    except KeyError:
        raise HTTPException(404, "Item não encontrado")
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    c.import_wake.set()
    with c.lock:
        return _item_view(c.imports._repo.get_item(item_id))


@router.get("/imports/{batch_id}")
def get_import(batch_id: str, c: Container = Depends(get_container)) -> ImportBatchView:
    with c.lock:
        batch = c.imports._repo.get_batch(batch_id)
    if batch is None:
        raise HTTPException(404, "Lote não encontrado")
    return _batch_view(batch)


@router.get("/prints/{print_id}")
def get_print(print_id: str, c: Container = Depends(get_container)) -> FileResponse:
    with c.lock:
        found = c.imports._prints.path(print_id)
    if found is None or not found[0].is_file():
        raise HTTPException(404, "Print não encontrado")
    path, mime = found
    return FileResponse(
        path, media_type=mime, headers={"Cache-Control": "private, max-age=31536000, immutable"}
    )
