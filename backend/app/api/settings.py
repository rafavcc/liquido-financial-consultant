from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError

from app.api import validation_messages
from app.deps import Container, get_container
from app.domain.settings import Settings

router = APIRouter(prefix="/settings")


@router.get("")
def get_settings(c: Container = Depends(get_container)) -> Settings:
    with c.lock:
        return c.settings.get()


@router.put("")
def put_settings(body: dict, c: Container = Depends(get_container)) -> Settings:
    try:
        settings = Settings.model_validate(body)
    except ValidationError as exc:
        raise HTTPException(422, validation_messages(exc)) from exc
    with c.lock:
        c.settings.save(settings)
    return settings


@router.post("/reset")
def reset_settings(c: Container = Depends(get_container)) -> Settings:
    with c.lock:
        return c.settings.reset()
