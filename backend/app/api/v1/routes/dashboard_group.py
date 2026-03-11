from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from datetime import date
from app.services.dashboard_service import dashboard_service
from app.services.monthly_compare_service import monthly_compare_service
from app.services.sales_performance_service import sales_performance_service
from app.core.security import get_current_active_user
from app.models.schemas import (
    DashboardResponse, MonthlyCompareResponse, SalesPerformanceResponse, User
)

router = APIRouter()

# 今日快报
@router.get("/today", response_model=DashboardResponse)
async def get_today_dashboard(
    date_str: Optional[date] = Query(None, alias="date"),
    current_user: User = Depends(get_current_active_user)
):
    """
    获取今日快报数据 - 包含5家公司数据和7天销售趋势
    """
    try:
        result = dashboard_service.get_today_dashboard(date_str)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取今日快报数据失败: {str(e)}")

# 月度对比
@router.get("/monthly-compare", response_model=MonthlyCompareResponse)
async def get_monthly_compare(
    year: int = Query(..., description="年份", ge=2020, le=2030),
    month: int = Query(..., description="月份", ge=1, le=12),
    current_user: User = Depends(get_current_active_user)
):
    """
    获取月度对比数据 - 5家公司P&L横向对比
    返回6个关键指标：收入、毛利率、净利率、人均产值、DSO、DIO
    """
    try:
        result = monthly_compare_service.get_monthly_compare(year, month)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取月度对比数据失败: {str(e)}")

# 销售绩效
@router.get("/sales-performance", response_model=SalesPerformanceResponse)
async def get_sales_performance(
    year: int = Query(..., description="年份", ge=2020, le=2030),
    month: int = Query(..., description="月份", ge=1, le=12),
    period_type: str = Query("month", description="统计周期类型: month/quarter/year"),
    current_user: User = Depends(get_current_active_user)
):
    """
    获取销售绩效数据 - 各公司目标vs实际完成情况
    支持按年/月/季度切换统计
    """
    try:
        result = sales_performance_service.get_sales_performance(year, month, period_type)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取销售绩效数据失败: {str(e)}")

# 缓存清除
@router.post("/cache/clear")
async def clear_dashboard_cache(
    date_str: Optional[date] = Query(None, alias="date"),
    current_user: User = Depends(get_current_active_user)
):
    """清除仪表板相关缓存"""
    try:
        from app.core.cache import cache_service
        import datetime
        
        if date_str:
            target_date = date_str.strftime('%Y-%m-%d')
        else:
            target_date = datetime.date.today().strftime('%Y-%m-%d')
        
        # 清除今日快报缓存
        cache_service.delete_pattern(f"dashboard:today:{target_date}*")
        
        # 清除月度对比缓存
        cache_service.delete_pattern(f"dashboard:monthly:*")
        
        # 清除销售绩效缓存
        cache_service.delete_pattern(f"dashboard:sales-performance:*")
        
        return {"message": "仪表板缓存已清除"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清除缓存失败: {str(e)}")