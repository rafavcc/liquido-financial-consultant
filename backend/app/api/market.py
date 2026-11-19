from fastapi import APIRouter, Depends

from app.deps import Container, get_container
from app.domain.simulation import MarketSummary, build_market_summary

router = APIRouter(prefix="/market")


def _summary(c: Container, force: bool) -> MarketSummary:
    settings, snapshot = c.snapshot(force=force)
    return build_market_summary(snapshot, c.context(settings, snapshot))


@router.get("")
def get_market(c: Container = Depends(get_container)) -> MarketSummary:
    return _summary(c, force=False)


@router.post("/refresh")
def refresh_market(c: Container = Depends(get_container)) -> MarketSummary:
    return _summary(c, force=True)
