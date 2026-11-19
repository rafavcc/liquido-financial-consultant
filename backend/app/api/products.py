import uuid

from fastapi import APIRouter, Depends, HTTPException, Response

from app.deps import Container, get_container
from app.domain.products.base import ProductData
from app.domain.products.validation import validate_product
from app.domain.sources import TesouroSource

router = APIRouter(prefix="/products")


def _validate(c: Container, data: ProductData) -> None:
    erros = validate_product(data, c.settings.get(), c.today_fn())
    if erros:
        raise HTTPException(422, erros)


def _not_found() -> HTTPException:
    return HTTPException(404, "Produto não encontrado")


@router.get("")
def list_products(c: Container = Depends(get_container)) -> list[ProductData]:
    with c.lock:
        return c.products.list()


@router.get("/tesouro")
def list_tesouro(c: Container = Depends(get_container)) -> list[ProductData]:
    settings, snapshot = c.snapshot()
    ctx = c.context(settings, snapshot)
    return [p.data for p in TesouroSource().load(ctx, snapshot)]


@router.post("")
def create_product(data: ProductData, c: Container = Depends(get_container)) -> ProductData:
    with c.lock:
        _validate(c, data)
        if data.id and c.products.get(data.id) is not None:
            raise HTTPException(409, "Já existe um produto com este id")
        return c.products.create(data)


@router.put("/{id}")
def update_product(id: str, data: ProductData, c: Container = Depends(get_container)) -> ProductData:
    with c.lock:
        if c.products.get(id) is None:
            raise _not_found()
        data = data.model_copy(update={"id": id})
        _validate(c, data)
        return c.products.update(id, data)


@router.delete("/{id}", status_code=204)
def delete_product(id: str, c: Container = Depends(get_container)) -> Response:
    with c.lock:
        if c.products.get(id) is None:
            raise _not_found()
        c.products.delete(id)
    return Response(status_code=204)


@router.post("/{id}/duplicate")
def duplicate_product(id: str, c: Container = Depends(get_container)) -> ProductData:
    with c.lock:
        original = c.products.get(id)
        if original is None:
            raise _not_found()
        copy = original.model_copy(
            update={"id": str(uuid.uuid4()), "nome": f"{original.nome} (cópia)", "exemplo": False}
        )
        return c.products.create(copy)
