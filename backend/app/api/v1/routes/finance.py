from fastapi import APIRouter, Depends, Query
from backend.app.core.security import get_current_active_user, check_company_permission
from backend.app.services.finance_service import finance_service
from backend.app.models.schemas import ARAging, ARQuery, FinanceExpense, FinanceCash, FinanceVoucher, User

router = APIRouter()

@router.get("/ar/aging", response_model=ARAging)
async def get_ar_aging(
    company_key: str = Query(...),
    current_user: User = Depends(get_current_active_user)
):
    """获取应收账款账龄分析"""
    check_company_permission(current_user, company_key)
    return finance_service.get_ar_aging(company_key)

@router.get("/ar/query", response_model=ARQuery)
async def get_ar_query(
    company_key: str = Query(...),
    start_date: str = Query(...),
    end_date: str = Query(...),
    current_user: User = Depends(get_current_active_user)
):
    """获取应收账款明细查询"""
    check_company_permission(current_user, company_key)
    return finance_service.get_ar_query(company_key, start_date, end_date)

@router.get("/expense", response_model=FinanceExpense)
async def get_expense_report(
    company_key: str = Query(...),
    year: int = Query(...),
    month: int = Query(...),
    current_user: User = Depends(get_current_active_user)
):
    """获取费用查询报告"""
    check_company_permission(current_user, company_key)
    return finance_service.get_expense_report(company_key, year, month)

@router.get("/cash", response_model=FinanceCash)
async def get_cash_report(
    company_key: str = Query(...),
    current_user: User = Depends(get_current_active_user)
):
    """获取资金查询报告"""
    check_company_permission(current_user, company_key)
    return finance_service.get_cash_report(company_key)

@router.get("/voucher", response_model=FinanceVoucher)
async def get_voucher_list(
    company_key: str = Query(...),
    start_date: str = Query(...),
    end_date: str = Query(...),
    current_user: User = Depends(get_current_active_user)
):
    """获取凭证列表"""
    check_company_permission(current_user, company_key)
    return finance_service.get_voucher_list(company_key, start_date, end_date)
