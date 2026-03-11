from typing import List, Dict, Any
from app.services.db_service import get_mssql_connection
import logging

logger = logging.getLogger(__name__)

class StockService:
    def get_stock_alerts(self, company_code: str) -> List[Dict[str, str]]:
        """
        Check for stock warnings.
        Logic: 
        1. Query 'v_未来可销天数' (Stock Days View).
        2. If days_available < 30 (Safety Stock), add warning.
        """
        alerts = []
        try:
            conn = get_mssql_connection(company_code)
            with conn.cursor(as_dict=True) as cursor:
                # Determine prefix based on country
                type_pfx = "00002" if "UGANDA" in company_code else "00003"
                
                # Query top 5 items with low stock days
                sql = f"""
                    SELECT TOP 5
                        CAST(v.存货名称 AS NVARCHAR(200)) AS stock_name,
                        v.总可销天数 AS days_available
                    FROM [v_未来可销天数] v
                    INNER JOIN Ptype c ON RTRIM(CAST(v.存货编号 AS NVARCHAR(50))) = RTRIM(CAST(c.UserCode AS NVARCHAR(50)))
                    WHERE RTRIM(CAST(c.typeid AS NVARCHAR(50))) LIKE '{type_pfx}%'
                      AND v.总可销天数 < 30
                    ORDER BY v.总可销天数 ASC
                """
                cursor.execute(sql)
                rows = cursor.fetchall()
                
                for row in rows:
                    alerts.append({
                        "type": "stock",
                        "msg": f"{row['stock_name']} 库存不足 ({row['days_available']}天)"
                    })
                    
        except Exception as e:
            logger.error(f"Error checking stock alerts for {company_code}: {e}")
            # Don't fail the whole dashboard for this
            pass
        finally:
            if 'conn' in locals():
                conn.close()
                
        return alerts

    def get_inventory_report(self, company_code: str, year: int, month: int) -> Dict[str, Any]:
        # Placeholder for Step 3
        return {}

stock_service = StockService()
