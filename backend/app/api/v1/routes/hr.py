from fastapi import APIRouter, Depends, Query
from backend.app.core.security import get_current_active_user, check_company_permission
from backend.app.services.hr_service import hr_service
from backend.app.models.schemas import HRReport, User

router = APIRouter()

@router.get("/report", response_model=HRReport)
async def get_hr_report(
    company_key: str = Query(...),
    year: int = Query(...),
    month: int = Query(...),
    current_user: User = Depends(get_current_active_user)
):
    """获取人员报告"""
    check_company_permission(current_user, company_key)
    return hr_service.get_hr_report(company_key, year, month)
