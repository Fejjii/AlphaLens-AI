"""Portfolio endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from alphalens.api.deps import PortfolioServiceDep
from alphalens.schemas.portfolio import PortfolioSummary

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("/summary", response_model=PortfolioSummary)
def get_portfolio_summary(service: PortfolioServiceDep) -> PortfolioSummary:
    return service.get_summary()
