from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from datetime import date
from backend.app.services.monthly_compare_service import monthly_compare_service
from backend.app.core.security import get_current_active_user
from backend.app.models.schemas import MonthlyCompareResponse, User

router = APIRouter()

@router.get("/monthly-compare", response_model=MonthlyCompareResponse)
async def get_monthly_compare(
    year: int = Query(..., description="年份", ge=2020, le=2030),
    month: int = Query(..., description="月份", ge=1, le=12),
    current_user: User = Depends(get_current_active_user)
):
    """
    获取月度对比数据 - 5家公司P&L横向对比
    
    返回6个关键指标：
    - 收入 (Revenue)
    - 毛利率 (Gross Margin %)
    - 净利率 (Net Margin %)
    - 人均产值 (Revenue per Person)
    - DSO (应收账款周转天数)
    - DIO (库存周转天数)
    
    指标说明：
    - 收入：本月销售收入
    - 毛利率：(收入-销售成本)/收入*100%
    - 净利率：净利润/收入*100%
    - 人均产值：收入/平均员工数
    - DSO：应收账款周转天数
    - DIO：库存周转天数
    """
    try:
        result = monthly_compare_service.get_monthly_compare(year, month)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取月度对比数据失败: {str(e)}")

@router.post("/monthly-compare/cache/clear")
async def clear_monthly_compare_cache(
    year: int = Query(..., description="年份"),
    month: int = Query(..., description="月份"),
    current_user: User = Depends(get_current_active_user)
):
    """清除月度对比缓存"""
    try:
        from backend.app.core.cache import cache_service
        
        cache_key = f"dashboard:monthly:{year}:{month}"
        cache_service.delete(cache_key)
        
        return {"message": f"{year}年{month}月度对比缓存已清除"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清除缓存失败: {str(e)}")