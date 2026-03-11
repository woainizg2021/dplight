from fastapi import APIRouter, Depends, HTTPException
from app.services.cache_service import get_cache_service, CacheService
from app.services.currency_service import get_currency_service, CurrencyService
from app.models.schemas import ExchangeRateResponse, CacheFlushRequest

router = APIRouter()

@router.get("/exchange-rates", response_model=ExchangeRateResponse)
async def get_exchange_rates(
    service: CurrencyService = Depends(get_currency_service)
):
    """
    Get latest exchange rates.
    """
    rates = service.get_latest_rates()
    return ExchangeRateResponse(rates=rates)

@router.post("/cache/flush")
async def flush_cache(
    request: CacheFlushRequest,
    cache: CacheService = Depends(get_cache_service)
):
    """
    Flush cache by pattern.
    """
    cache.delete_pattern(request.pattern)
    return {"message": f"Cache flushed for pattern: {request.pattern}"}
