from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, Literal
from datetime import date
from app.services.sales_performance_service import sales_performance_service
from app.core.security import get_current_active_user
from app.models.schemas import SalesPerformanceResponse, User

router = APIRouter()

@router.get("/sales-performance", response_model=SalesPerformanceResponse)
async def get_sales_performance(
    year: int = Query(..., description="年份", ge=2020, le=2030),
    month: int = Query(..., description="月份", ge=1, le=12),
    period_type: Literal["month", "quarter", "year"] = Query("month", description="统计周期类型"),
    current_user: User = Depends(get_current_active_user)
):
    """
    获取销售绩效数据 - 各公司目标vs实际完成情况
    
    支持按年/月/季度切换统计：
    - month: 月度统计 (默认)
    - quarter: 季度统计 
    - year: 年度统计
    
    返回指标：
    - target: 销售目标
    - actual: 实际销售额
    - completion_rate: 完成率 (%)
    - yoy: 同比增长率 (%)
    - mom: 环比增长率 (%)
    """
    try:
        result = sales_performance_service.get_sales_performance(year, month, period_type)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取销售绩效数据失败: {str(e)}")

@router.post("/sales-performance/cache/clear")
async def clear_sales_performance_cache(
    year: int = Query(..., description="年份"),
    month: int = Query(..., description="月份"),
    period_type: Literal["month", "quarter", "year"] = Query("month", description="统计周期类型"),
    current_user: User = Depends(get_current_active_user)
):
    """清除销售绩效缓存"""
    try:
        from app.core.cache import cache_service
        
        cache_key = f"dashboard:sales-performance:{year}:{month}:{period_type}"
        cache_service.delete(cache_key)
        
        return {"message": f"{year}年{month}月销售绩效缓存已清除"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清除缓存失败: {str(e)}")