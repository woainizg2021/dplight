from fastapi import APIRouter, Depends, Query
from app.core.security import get_current_active_user, check_company_permission
from app.services.production_service import production_service
from app.models.schemas import ProductionOverview, User

router = APIRouter()

@router.get("/overview", response_model=ProductionOverview)
async def get_production_overview(
    company_key: str = Query(...),
    year: int = Query(...),
    month: int = Query(...),
    current_user: User = Depends(get_current_active_user)
):
    """获取生产概览报告"""
    check_company_permission(current_user, company_key)
    return production_service.get_production_overview(company_key, year, month)
