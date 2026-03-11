from typing import Dict, Any, Optional, List
from datetime import datetime, date
from app.db.mssql import get_db_connection
from app.db.mysql import get_mysql_connection
from app.models.schemas import ProductionOverview
import logging

logger = logging.getLogger(__name__)

class ProductionService:
    def get_production_overview(self, company_key: str, year: int, month: int) -> ProductionOverview:
        """
        Get production overview including machine output, utilization, defect rates,
        and 3-month trends for a specific company.
        """
        try:
            # Get MySQL connection for production data (Tencent Cloud)
            mysql_conn = get_mysql_connection()
            
            with mysql_conn.cursor(dictionary=True) as cursor:
                # 1. Get machine data
                machines = self._get_machine_data(cursor, company_key, year, month)
                
                # 2. Get 3-month trends
                trend = self._get_production_trends(cursor, company_key, year, month)
                
                return ProductionOverview(
                    company_key=company_key,
                    machines=machines,
                    trend=trend
                )
                
        except Exception as e:
            logger.error(f"Error fetching production overview for {company_key}: {e}")
            raise e
        finally:
            if 'mysql_conn' in locals():
                mysql_conn.close()
    
    def _get_machine_data(self, cursor, company_key: str, year: int, month: int) -> List[Dict[str, Any]]:
        """Get machine production data."""
        
        # Determine equipment types based on company
        equipment_types = self._get_equipment_types(company_key)
        
        machines = []
        
        for equipment_type in equipment_types:
            # Get machine data for this equipment type
            sql_machine = """
                SELECT 
                    equipment_name,
                    equipment_type,
                    output_quantity,
                    planned_quantity,
                    operating_hours,
                    planned_hours,
                    defect_quantity,
                    defect_reasons
                FROM production_equipment_data 
                WHERE company_key = %s 
                AND equipment_type = %s
                AND year = %s 
                AND month = %s
                ORDER BY output_quantity DESC
            """
            
            cursor.execute(sql_machine, (company_key, equipment_type, year, month))
            rows = cursor.fetchall()
            
            for row in rows:
                # Calculate utilization rate
                utilization_rate = (row['operating_hours'] / row['planned_hours'] * 100) if row['planned_hours'] > 0 else 0
                
                # Calculate defect rate
                defect_rate = (row['defect_quantity'] / row['output_quantity'] * 100) if row['output_quantity'] > 0 else 0
                
                machines.append({
                    "name": row['equipment_name'],
                    "type": row['equipment_type'],
                    "output": row['output_quantity'],
                    "planned": row['planned_quantity'],
                    "utilization_rate": utilization_rate,
                    "defect_rate": defect_rate,
                    "operating_hours": row['operating_hours'],
                    "defect_quantity": row['defect_quantity'],
                    "defect_reasons": row['defect_reasons']
                })
        
        return machines
    
    def _get_equipment_types(self, company_key: str) -> List[str]:
        """Get equipment types based on company."""
        
        # Equipment mapping by company
        equipment_map = {
            'UGANDA': ['注塑机', '冲压机', '组装线', '包装线'],
            'NIGERIA': ['注塑机', '冲压机', '组装线', '包装线'],
            'KENYA': ['注塑机', '冲压机', '组装线', '包装线'],
            'KENYA_AUDIO': ['音箱组装线', '测试设备', '包装线', '质检设备'],
            'DRC': ['注塑机', '冲压机', '组装线', '包装线']
        }
        
        return equipment_map.get(company_key, ['注塑机', '冲压机', '组装线'])
    
    def _get_production_trends(self, cursor, company_key: str, year: int, month: int) -> Dict[str, List[float]]:
        """Get 3-month production trends."""
        
        trends = {
            "output": [],
            "utilization": [],
            "defect_rate": [],
            "months": []
        }
        
        # Get last 3 months data
        for i in range(2, -1, -1):  # 2 months ago, 1 month ago, current month
            if month - i <= 0:
                trend_year = year - 1
                trend_month = 12 + (month - i)
            else:
                trend_year = year
                trend_month = month - i
            
            # Get aggregated data for this month
            sql_trend = """
                SELECT 
                    SUM(output_quantity) as total_output,
                    AVG(utilization_rate) as avg_utilization,
                    AVG(defect_rate) as avg_defect_rate
                FROM production_monthly_summary 
                WHERE company_key = %s 
                AND year = %s 
                AND month = %s
            """
            
            cursor.execute(sql_trend, (company_key, trend_year, trend_month))
            row = cursor.fetchone()
            
            if row and row['total_output'] is not None:
                trends["output"].append(float(row['total_output']))
                trends["utilization"].append(float(row['avg_utilization']) if row['avg_utilization'] else 0)
                trends["defect_rate"].append(float(row['avg_defect_rate']) if row['avg_defect_rate'] else 0)
            else:
                trends["output"].append(0)
                trends["utilization"].append(0)
                trends["defect_rate"].append(0)
            
            trends["months"].append(f"{trend_year}-{trend_month:02d}")
        
        return trends

production_service = ProductionService()