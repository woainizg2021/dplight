from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from datetime import date
from backend.app.services.db_service import get_mssql_connection
from backend.app.services.cache_service import get_cache_service, CacheService
from backend.app.services.currency_service import get_currency_service, CurrencyService
from backend.app.models.schemas import DashboardData
from backend.app.config import DASHBOARD_CACHE_TTL
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/{company_code}", response_model=DashboardData)
async def get_dashboard_data(
    company_code: str,
    date_str: Optional[str] = Query(None, alias="date"),
    cache: CacheService = Depends(get_cache_service),
    currency_service: CurrencyService = Depends(get_currency_service)
):
    """
    Get dashboard data for a specific company.
    """
    if not date_str:
        date_str = date.today().strftime('%Y-%m-%d')

    cache_key = cache.get_dashboard_key(company_code, date_str)
    cached_data = cache.get(cache_key)
    if cached_data:
        return cached_data

    conn = get_mssql_connection(company_code)
    try:
        with conn.cursor() as cursor:
            # 1. Sales Today (VchType 11)
            sql_sales = f"SELECT SUM(Total) FROM Dlyndx WHERE VchType = 11 AND Draft = 2 AND Date = %s"
            cursor.execute(sql_sales, (date_str,))
            row = cursor.fetchone()
            sales_today = float(row[0]) if row and row[0] else 0.0

            # 2. Sales Month (Start of month to date)
            start_month = f"{date_str[:7]}-01"
            sql_sales_m = f"SELECT SUM(Total) FROM Dlyndx WHERE VchType = 11 AND Draft = 2 AND Date BETWEEN %s AND %s"
            cursor.execute(sql_sales_m, (start_month, f"{date_str} 23:59:59"))
            row = cursor.fetchone()
            sales_month = float(row[0]) if row and row[0] else 0.0

            # 3. Production Today (VchType 174)
            # Using ABS logic as per recent fixes
            sql_prod = f"""
                SELECT SUM(ABS(o.Qty)) 
                FROM DlyOther o JOIN Dlyndx n ON o.VchCode = n.VchCode
                WHERE n.VchType = 174 AND n.Draft = 2 AND n.Date = %s
            """
            cursor.execute(sql_prod, (date_str,))
            row = cursor.fetchone()
            prod_today = float(row[0]) if row and row[0] else 0.0
            has_production = prod_today > 0

            # 4. Balance (Bank + Cash)
            sql_fund = """
                SELECT SUM(Amt) FROM (
                    SELECT SUM(ISNULL(DebitTotal,0) - ISNULL(CreditTotal,0)) as Amt FROM DlyBank
                    UNION ALL
                    SELECT SUM(ISNULL(DebitTotal,0) - ISNULL(CreditTotal,0)) as Amt FROM DlyCash
                ) t
            """
            cursor.execute(sql_fund)
            row = cursor.fetchone()
            balance = float(row[0]) if row and row[0] else 0.0

            # Warnings logic
            warnings = []
            if not has_production and company_code != 'DRC': # DRC exception as per original logic
                warnings.append("停机预警")
            
            # TODO: Add inventory and AR warnings

            data = DashboardData(
                company_code=company_code,
                date=date_str,
                sales_today=sales_today,
                sales_month=sales_month,
                prod_today=prod_today,
                balance=balance,
                has_production=has_production,
                warnings=warnings,
                currency="Unknown" # Populate from config later if needed
            )
            
            # Cache the result
            cache.set(cache_key, data.model_dump(), DASHBOARD_CACHE_TTL)
            
            return data

    except Exception as e:
        logger.error(f"Error fetching dashboard data for {company_code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
