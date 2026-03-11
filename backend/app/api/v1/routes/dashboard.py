from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from datetime import date
from app.services.dashboard_service import dashboard_service
from app.core.security import get_current_active_user
from app.models.schemas import DashboardResponse, User

router = APIRouter()

@router.get("/today", response_model=DashboardResponse)
async def get_today_dashboard(
    date_str: Optional[date] = Query(None, alias="date"),
    current_user: User = Depends(get_current_active_user)
):
    """
    获取今日快报数据 - 包含5家公司数据和7天销售趋势
    
    返回格式:
    {
        "updated_at": "2026-03-09 14:30:00",
        "companies": [
            {
                "key": "UGANDA",
                "short_name": "乌干达",
                "full_name": "乌干达灯具制造",
                "currency": "UGX",
                "today_sales": 0,
                "mtd_sales": 0,
                "mtd_target": 0,
                "today_production": 0,
                "bank_balance": 0,
                "alerts": []
            }
        ],
        "sales_trend": {
            "dates": ["2026-03-03", ...],
            "UGANDA": [0, ...],
            "NIGERIA": [0, ...],
            "KENYA": [0, ...],
            "KENYA_AUDIO": [0, ...],
            "DRC": [0, ...]
        }
    }
    """
    try:
        result = dashboard_service.get_today_dashboard(date_str)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取今日快报数据失败: {str(e)}")

@router.post("/cache/clear")
async def clear_dashboard_cache(
    current_user: User = Depends(get_current_active_user)
):
    """清除仪表板缓存"""
    try:
        from app.core.cache import cache_service
        import datetime
        
        today = datetime.date.today().strftime('%Y-%m-%d')
        cache_service.delete_pattern(f"dashboard:today:{today}*")
        
        return {"message": "仪表板缓存已清除"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清除缓存失败: {str(e)}")