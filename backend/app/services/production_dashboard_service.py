from typing import Dict, Any, Optional, List
from datetime import datetime, date
from app.db.mssql import get_db_connection
from app.db.mysql import get_mysql_connection
from app.models.schemas import ProductionCapacity, ProductionWorkgroup, WIPWarning, QualityTrend
import logging

logger = logging.getLogger(__name__)

class ProductionDashboardService:
    """
    Service for production dashboard functionality migrated from Streamlit modules.
    This service provides comprehensive production analysis including capacity, workgroup rankings,
    WIP warnings, and quality trends.
    """
    
    def get_production_capacity_overview(self, company_key: str, year: int, month: int) -> ProductionCapacity:
        """
        Get production capacity overview with equipment utilization and output analysis.
        Migrated from production_capacity.py Streamlit module.
        """
        try:
            # Get MySQL connection for production data
            mysql_conn = get_mysql_connection()
            
            with mysql_conn.cursor(dictionary=True) as cursor:
                # Get capacity utilization data
                sql_capacity = """
                    SELECT 
                        equipment_name,
                        equipment_type,
                        planned_capacity,
                        actual_output,
                        utilization_rate,
                        efficiency_rate,
                        downtime_hours,
                        operating_hours,
                        capacity_month,
                        capacity_year
                    FROM production_capacity 
                    WHERE company_key = %s 
                    AND capacity_year = %s 
                    AND capacity_month = %s
                    ORDER BY utilization_rate DESC
                """
                
                cursor.execute(sql_capacity, (company_key, year, month))
                rows = cursor.fetchall()
                
                capacity_data = []
                for row in rows:
                    capacity_data.append({
                        "equipment_name": row['equipment_name'],
                        "equipment_type": row['equipment_type'],
                        "planned_capacity": float(row['planned_capacity'] or 0),
                        "actual_output": float(row['actual_output'] or 0),
                        "utilization_rate": float(row['utilization_rate'] or 0),
                        "efficiency_rate": float(row['efficiency_rate'] or 0),
                        "downtime_hours": float(row['downtime_hours'] or 0),
                        "operating_hours": float(row['operating_hours'] or 0),
                        "capacity_month": row['capacity_month'],
                        "capacity_year": row['capacity_year']
                    })
                
                # Calculate summary statistics
                summary = self._calculate_capacity_summary(capacity_data)
                
                return ProductionCapacity(
                    company_key=company_key,
                    year=year,
                    month=month,
                    capacity_data=capacity_data,
                    summary=summary
                )
                
        except Exception as e:
            logger.error(f"Error fetching production capacity for {company_key}: {e}")
            raise e
        finally:
            if 'mysql_conn' in locals():
                mysql_conn.close()
    
    def get_production_workgroup_rankings(self, company_key: str, year: int, month: int) -> List[ProductionWorkgroup]:
        """
        Get production workgroup performance rankings.
        Migrated from production_workgroup_rank.py Streamlit module.
        """
        try:
            mysql_conn = get_mysql_connection()
            
            with mysql_conn.cursor(dictionary=True) as cursor:
                # Get workgroup performance data
                sql_workgroups = """
                    SELECT 
                        workgroup_name,
                        workgroup_code,
                        production_quantity,
                        production_value,
                        efficiency_rate,
                        quality_rate,
                        attendance_rate,
                        avg_completion_time,
                        ranking_score,
                        rank_position
                    FROM production_workgroup_performance 
                    WHERE company_key = %s 
                    AND year = %s 
                    AND month = %s
                    ORDER BY ranking_score DESC
                """
                
                cursor.execute(sql_workgroups, (company_key, year, month))
                rows = cursor.fetchall()
                
                workgroups = []
                for row in rows:
                    workgroups.append({
                        "workgroup_name": row['workgroup_name'],
                        "workgroup_code": row['workgroup_code'],
                        "production_quantity": float(row['production_quantity'] or 0),
                        "production_value": float(row['production_value'] or 0),
                        "efficiency_rate": float(row['efficiency_rate'] or 0),
                        "quality_rate": float(row['quality_rate'] or 0),
                        "attendance_rate": float(row['attendance_rate'] or 0),
                        "avg_completion_time": float(row['avg_completion_time'] or 0),
                        "ranking_score": float(row['ranking_score'] or 0),
                        "rank_position": int(row['rank_position'] or 0)
                    })
                
                return workgroups
                
        except Exception as e:
            logger.error(f"Error fetching workgroup rankings for {company_key}: {e}")
            raise e
        finally:
            if 'mysql_conn' in locals():
                mysql_conn.close()
    
    def get_wip_warnings(self, company_key: str) -> List[WIPWarning]:
        """
        Get Work-in-Process (WIP) backlog warnings and alerts.
        Migrated from wip_warning.py Streamlit module.
        """
        try:
            mysql_conn = get_mysql_connection()
            
            with mysql_conn.cursor(dictionary=True) as cursor:
                # Get WIP backlog data
                sql_wip = """
                    SELECT 
                        work_order_number,
                        product_name,
                        planned_quantity,
                        completed_quantity,
                        wip_quantity,
                        backlog_days,
                        estimated_completion_date,
                        warning_level,
                        bottleneck_process,
                        responsible_workgroup,
                        last_update_time
                    FROM wip_backlog_alerts 
                    WHERE company_key = %s 
                    AND warning_level IN ('HIGH', 'MEDIUM', 'LOW')
                    ORDER BY 
                        CASE warning_level 
                            WHEN 'HIGH' THEN 1 
                            WHEN 'MEDIUM' THEN 2 
                            WHEN 'LOW' THEN 3 
                        END,
                        backlog_days DESC
                """
                
                cursor.execute(sql_wip, (company_key,))
                rows = cursor.fetchall()
                
                wip_warnings = []
                for row in rows:
                    wip_warnings.append({
                        "work_order_number": row['work_order_number'],
                        "product_name": row['product_name'],
                        "planned_quantity": int(row['planned_quantity'] or 0),
                        "completed_quantity": int(row['completed_quantity'] or 0),
                        "wip_quantity": int(row['wip_quantity'] or 0),
                        "backlog_days": int(row['backlog_days'] or 0),
                        "estimated_completion_date": row['estimated_completion_date'].strftime('%Y-%m-%d') if row['estimated_completion_date'] else '',
                        "warning_level": row['warning_level'],
                        "bottleneck_process": row['bottleneck_process'],
                        "responsible_workgroup": row['responsible_workgroup'],
                        "last_update_time": row['last_update_time'].strftime('%Y-%m-%d %H:%M:%S') if row['last_update_time'] else ''
                    })
                
                return wip_warnings
                
        except Exception as e:
            logger.error(f"Error fetching WIP warnings for {company_key}: {e}")
            raise e
        finally:
            if 'mysql_conn' in locals():
                mysql_conn.close()
    
    def get_quality_trends(self, company_key: str, days: int = 30) -> QualityTrend:
        """
        Get quality trends and defect analysis for specified period.
        Migrated from quality_trend.py Streamlit module.
        """
        try:
            mysql_conn = get_mysql_connection()
            
            with mysql_conn.cursor(dictionary=True) as cursor:
                # Get quality trend data
                sql_quality = """
                    SELECT 
                        date_recorded,
                        total_production,
                        good_quantity,
                        defect_quantity,
                        defect_rate,
                        top_defect_types,
                        quality_score,
                        inspection_pass_rate,
                        customer_complaints
                    FROM quality_daily_metrics 
                    WHERE company_key = %s 
                    AND date_recorded >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
                    ORDER BY date_recorded DESC
                """
                
                cursor.execute(sql_quality, (company_key, days))
                rows = cursor.fetchall()
                
                quality_data = []
                for row in rows:
                    quality_data.append({
                        "date_recorded": row['date_recorded'].strftime('%Y-%m-%d') if row['date_recorded'] else '',
                        "total_production": int(row['total_production'] or 0),
                        "good_quantity": int(row['good_quantity'] or 0),
                        "defect_quantity": int(row['defect_quantity'] or 0),
                        "defect_rate": float(row['defect_rate'] or 0),
                        "top_defect_types": row['top_defect_types'],
                        "quality_score": float(row['quality_score'] or 0),
                        "inspection_pass_rate": float(row['inspection_pass_rate'] or 0),
                        "customer_complaints": int(row['customer_complaints'] or 0)
                    })
                
                # Calculate quality summary
                summary = self._calculate_quality_summary(quality_data)
                
                return QualityTrend(
                    company_key=company_key,
                    period_days=days,
                    quality_data=quality_data,
                    summary=summary
                )
                
        except Exception as e:
            logger.error(f"Error fetching quality trends for {company_key}: {e}")
            raise e
        finally:
            if 'mysql_conn' in locals():
                mysql_conn.close()
    
    def _calculate_capacity_summary(self, capacity_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate capacity utilization summary statistics."""
        if not capacity_data:
            return {
                "total_equipment": 0,
                "avg_utilization_rate": 0,
                "total_planned_capacity": 0,
                "total_actual_output": 0,
                "overall_efficiency": 0,
                "low_utilization_count": 0
            }
        
        total_equipment = len(capacity_data)
        avg_utilization_rate = sum(c['utilization_rate'] for c in capacity_data) / total_equipment
        total_planned_capacity = sum(c['planned_capacity'] for c in capacity_data)
        total_actual_output = sum(c['actual_output'] for c in capacity_data)
        overall_efficiency = (total_actual_output / total_planned_capacity * 100) if total_planned_capacity > 0 else 0
        low_utilization_count = len([c for c in capacity_data if c['utilization_rate'] < 70])
        
        return {
            "total_equipment": total_equipment,
            "avg_utilization_rate": avg_utilization_rate,
            "total_planned_capacity": total_planned_capacity,
            "total_actual_output": total_actual_output,
            "overall_efficiency": overall_efficiency,
            "low_utilization_count": low_utilization_count
        }
    
    def _calculate_quality_summary(self, quality_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate quality trend summary statistics."""
        if not quality_data:
            return {
                "avg_defect_rate": 0,
                "avg_quality_score": 0,
                "avg_inspection_pass_rate": 0,
                "total_customer_complaints": 0,
                "trend_direction": "stable"
            }
        
        avg_defect_rate = sum(q['defect_rate'] for q in quality_data) / len(quality_data)
        avg_quality_score = sum(q['quality_score'] for q in quality_data) / len(quality_data)
        avg_inspection_pass_rate = sum(q['inspection_pass_rate'] for q in quality_data) / len(quality_data)
        total_customer_complaints = sum(q['customer_complaints'] for q in quality_data)
        
        # Determine trend direction
        if len(quality_data) >= 2:
            recent_defect_rate = quality_data[0]['defect_rate']
            previous_defect_rate = quality_data[-1]['defect_rate']
            if recent_defect_rate < previous_defect_rate:
                trend_direction = "improving"
            elif recent_defect_rate > previous_defect_rate:
                trend_direction = "declining"
            else:
                trend_direction = "stable"
        else:
            trend_direction = "stable"
        
        return {
            "avg_defect_rate": avg_defect_rate,
            "avg_quality_score": avg_quality_score,
            "avg_inspection_pass_rate": avg_inspection_pass_rate,
            "total_customer_complaints": total_customer_complaints,
            "trend_direction": trend_direction
        }

production_dashboard_service = ProductionDashboardService()