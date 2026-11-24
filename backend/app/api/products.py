import uuid

from fastapi import APIRouter, Depends, HTTPException, Response

from app.deps import Container, get_container
from app.domain.offers import is_expired, offer_age_days
from app.domain.products.base import ProductData
from app.domain.products.validation import validate_product
from app.domain.sources import TesouroSource

class ProductView(ProductData):
    idade_dias: int | None = None
    expirada: bool = False


router = APIRouter(prefix="/products")


def _validate(c: Container, data: ProductData) -> None:
    erros = validate_product(data, c.settings.get(), c.today_fn())
    if erros:
        raise HTTPException(422, erros)


def _not_found() -> HTTPException:
    return HTTPException(404, "Produto não encontrado")


@router.get("")
def list_products(c: Container = Depends(get_container)) -> list[ProductView]:
    with c.lock:
        items, settings = c.products.list(), c.settings.get()
    today = c.today_fn()
    return [
        ProductView(
            **p.model_dump(),
            idade_dias=offer_age_days(p, today),
            expirada=is_expired(p, settings, today),
        )
        for p in items
    ]


@router.get("/tesouro")
def list_tesouro(c: Container = Depends(get_container)) -> list[ProductData]:
    settings, snapshot = c.snapshot()
    ctx = c.context(settings, snapshot)
    return [p.data for p in TesouroSource().load(ctx, snapshot)]


@router.post("", status_code=201)
def create_product(data: ProductData, c: Container = Depends(get_container)) -> ProductData:
    with c.lock:
        data = data.model_copy(
            update={"exemplo": False, "data_registro": c.today_fn(), "origem": "MANUAL", "print_id": None}
        )
        _validate(c, data)
        if data.id and c.products.get(data.id) is not None:
            raise HTTPException(409, "Já existe um produto com este id")
        return c.products.create(data)


@router.put("/{id}")
def update_product(id: str, data: ProductData, c: Container = Depends(get_container)) -> ProductData:
    with c.lock:
        stored = c.products.get(id)
        if stored is None:
            raise _not_found()
        data = data.model_copy(
            update={
                "id": id,
                "data_registro": stored.data_registro,
                "origem": stored.origem,
                "print_id": stored.print_id,
                "juros_periodicos": stored.juros_periodicos,
                "amortizacao": stored.amortizacao,
            }
        )
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
            update={
                "id": str(uuid.uuid4()),
                "nome": f"{original.nome} (cópia)",
                "exemplo": False,
                "data_registro": c.today_fn(),
                "origem": "MANUAL",
                "print_id": None,
            }
        )
        return c.products.create(copy)
