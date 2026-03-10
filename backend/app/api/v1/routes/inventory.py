from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Optional
from backend.app.core.security import get_current_active_user, check_company_permission
from backend.app.services.inventory_service import inventory_service, inventory_analysis_service
from backend.app.models.schemas import InventoryReport, InventoryAnalysis, User

router = APIRouter()

@router.get("/report", response_model=InventoryReport)
async def get_inventory_report(
    company_key: str = Query(...),
    year: int = Query(...),
    month: int = Query(...),
    current_user: User = Depends(get_current_active_user)
):
    """获取库存综合报告"""
    check_company_permission(current_user, company_key)
    return inventory_service.get_inventory_report(company_key, year, month)

@router.get("/raw-material")
async def get_raw_materials(
    company_key: str = Query(...),
    year: int = Query(...),
    month: int = Query(...),
    current_user: User = Depends(get_current_active_user)
):
    """获取原材料库存查询"""
    check_company_permission(current_user, company_key)
    return inventory_service.get_raw_materials(company_key, year, month)

@router.get("/finished-goods")
async def get_finished_goods(
    company_key: str = Query(...),
    year: int = Query(...),
    month: int = Query(...),
    current_user: User = Depends(get_current_active_user)
):
    """获取成品库存查询"""
    check_company_permission(current_user, company_key)
    return inventory_service.get_finished_goods(company_key, year, month)

@router.get("/inout-detail")
async def get_inout_detail(
    company_key: str = Query(...),
    start_date: str = Query(...),
    end_date: str = Query(...),
    current_user: User = Depends(get_current_active_user)
):
    """获取出入库明细 (Placeholder)"""
    check_company_permission(current_user, company_key)
    # TODO: Implement in service
    return {"message": "Not implemented yet"}

@router.get("/analysis", response_model=InventoryAnalysis)
async def get_inventory_analysis(
    company_key: str = Query(...),
    year: int = Query(...),
    month: int = Query(...),
    current_user: User = Depends(get_current_active_user)
):
    """获取产销存分析"""
    check_company_permission(current_user, company_key)
    return inventory_analysis_service.get_inventory_analysis(company_key, year, month)
