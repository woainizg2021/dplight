from typing import Dict, Any, Optional, List
from datetime import datetime, date
from backend.app.db.mssql import get_db_connection
from backend.app.db.mysql import get_mysql_connection
from backend.app.models.schemas import HRReport, InventoryAnalysis
import logging

logger = logging.getLogger(__name__)

class HRService:
    def get_hr_report(self, company_key: str, year: int, month: int) -> HRReport:
        """
        Get HR report including department staffing, attendance, absence rates, and labor costs.
        """
        try:
            # Get MySQL connection for HR data
            mysql_conn = get_mysql_connection()
            
            with mysql_conn.cursor(dictionary=True) as cursor:
                # 1. Get department data
                departments = self._get_department_data(cursor, company_key, year, month)
                
                # 2. Get attendance data
                attendance = self._get_attendance_data(cursor, company_key, year, month)
                
                # 3. Get labor cost data
                labor_costs = self._get_labor_cost_data(cursor, company_key, year, month)
                
                return HRReport(
                    company_key=company_key,
                    year=year,
                    month=month,
                    departments=departments,
                    attendance=attendance,
                    labor_costs=labor_costs
                )
                
        except Exception as e:
            logger.error(f"Error fetching HR report for {company_key}: {e}")
            raise e
        finally:
            if 'mysql_conn' in locals():
                mysql_conn.close()
    
    def _get_department_data(self, cursor, company_key: str, year: int, month: int) -> List[Dict[str, Any]]:
        """Get department staffing data."""
        
        sql_departments = """
            SELECT 
                d.department_name,
                d.department_code,
                d.planned_headcount,
                d.actual_headcount,
                d.vacancy_count,
                d.avg_salary,
                d.total_salary_budget
            FROM hr_departments d
            WHERE d.company_key = %s 
            AND d.year = %s 
            AND d.month = %s
            ORDER BY d.total_salary_budget DESC
        """
        
        cursor.execute(sql_departments, (company_key, year, month))
        rows = cursor.fetchall()
        
        departments = []
        for row in rows:
            departments.append({
                "department_name": row['department_name'],
                "department_code": row['department_code'],
                "planned_headcount": int(row['planned_headcount'] or 0),
                "actual_headcount": int(row['actual_headcount'] or 0),
                "vacancy_count": int(row['vacancy_count'] or 0),
                "vacancy_rate": (row['vacancy_count'] / row['planned_headcount'] * 100) if row['planned_headcount'] > 0 else 0,
                "avg_salary": float(row['avg_salary'] or 0),
                "total_salary_budget": float(row['total_salary_budget'] or 0)
            })
        
        return departments
    
    def _get_attendance_data(self, cursor, company_key: str, year: int, month: int) -> Dict[str, Any]:
        """Get attendance and absence data."""
        
        sql_attendance = """
            SELECT 
                SUM(a.present_days) as total_present_days,
                SUM(a.absent_days) as total_absent_days,
                SUM(a.leave_days) as total_leave_days,
                SUM(a.overtime_hours) as total_overtime_hours,
                COUNT(DISTINCT a.employee_id) as total_employees,
                AVG(a.attendance_rate) as avg_attendance_rate,
                AVG(a.absence_rate) as avg_absence_rate
            FROM hr_attendance a
            WHERE a.company_key = %s 
            AND a.year = %s 
            AND a.month = %s
        """
        
        cursor.execute(sql_attendance, (company_key, year, month))
        row = cursor.fetchone()
        
        return {
            "total_present_days": int(row['total_present_days'] or 0),
            "total_absent_days": int(row['total_absent_days'] or 0),
            "total_leave_days": int(row['total_leave_days'] or 0),
            "total_overtime_hours": float(row['total_overtime_hours'] or 0),
            "total_employees": int(row['total_employees'] or 0),
            "avg_attendance_rate": float(row['avg_attendance_rate'] or 0),
            "avg_absence_rate": float(row['avg_absence_rate'] or 0)
        }
    
    def _get_labor_cost_data(self, cursor, company_key: str, year: int, month: int) -> Dict[str, Any]:
        """Get labor cost analysis data."""
        
        sql_labor_cost = """
            SELECT 
                SUM(l.base_salary) as total_base_salary,
                SUM(l.overtime_pay) as total_overtime_pay,
                SUM(l.bonus) as total_bonus,
                SUM(l.benefits) as total_benefits,
                SUM(l.total_cost) as total_labor_cost,
                AVG(l.cost_per_employee) as avg_cost_per_employee,
                l.cost_as_percentage_of_revenue
            FROM hr_labor_costs l
            WHERE l.company_key = %s 
            AND l.year = %s 
            AND l.month = %s
        """
        
        cursor.execute(sql_labor_cost, (company_key, year, month))
        row = cursor.fetchone()
        
        return {
            "total_base_salary": float(row['total_base_salary'] or 0),
            "total_overtime_pay": float(row['total_overtime_pay'] or 0),
            "total_bonus": float(row['total_bonus'] or 0),
            "total_benefits": float(row['total_benefits'] or 0),
            "total_labor_cost": float(row['total_labor_cost'] or 0),
            "avg_cost_per_employee": float(row['avg_cost_per_employee'] or 0),
            "cost_as_percentage_of_revenue": float(row['cost_as_percentage_of_revenue'] or 0)
        }

class InventoryAnalysisService:
    def get_inventory_analysis(self, company_key: str, year: int, month: int) -> InventoryAnalysis:
        """
        Get production-sales-inventory analysis for comprehensive business insights.
        """
        try:
            # Get MSSQL connection for inventory data
            conn = get_db_connection(company_key)
            
            with conn.cursor(as_dict=True) as cursor:
                # 1. Production data
                production_data = self._get_production_data(cursor, year, month)
                
                # 2. Sales data
                sales_data = self._get_sales_data(cursor, year, month)
                
                # 3. Inventory data
                inventory_data = self._get_inventory_data(cursor, year, month)
                
                # 4. Analysis calculations
                analysis = self._calculate_analysis(production_data, sales_data, inventory_data)
                
                return InventoryAnalysis(
                    company_key=company_key,
                    year=year,
                    month=month,
                    production=production_data,
                    sales=sales_data,
                    inventory=inventory_data,
                    analysis=analysis
                )
                
        except Exception as e:
            logger.error(f"Error fetching inventory analysis for {company_key}: {e}")
            raise e
        finally:
            if 'conn' in locals():
                conn.close()
    
    def _get_production_data(self, cursor, year: int, month: int) -> Dict[str, Any]:
        """Get production data for the period."""
        
        start_date = f"{year}-{month:02d}-01"
        end_date = f"{year}-{month:02d}-31"
        
        sql_production = """
            SELECT 
                COUNT(DISTINCT p.VchCode) as production_orders,
                SUM(ABS(p.Qty)) as total_production_qty,
                SUM(ABS(p.Total)) as total_production_value,
                AVG(ABS(p.Price)) as avg_production_price
            FROM DlySC p
            JOIN DlyndxSC ndx ON p.VchCode = ndx.VchCode
            WHERE ndx.VchType = 171  -- Production orders
            AND ndx.Draft = 2
            AND ndx.Date BETWEEN %s AND %s
        """
        
        cursor.execute(sql_production, (start_date, end_date))
        row = cursor.fetchone()
        
        return {
            "production_orders": int(row['production_orders'] or 0),
            "total_production_qty": float(row['total_production_qty'] or 0),
            "total_production_value": float(row['total_production_value'] or 0),
            "avg_production_price": float(row['avg_production_price'] or 0)
        }
    
    def _get_sales_data(self, cursor, year: int, month: int) -> Dict[str, Any]:
        """Get sales data for the period."""
        
        start_date = f"{year}-{month:02d}-01"
        end_date = f"{year}-{month:02d}-31"
        
        sql_sales = """
            SELECT 
                COUNT(DISTINCT s.VchCode) as sales_orders,
                SUM(ABS(s.Qty)) as total_sales_qty,
                SUM(ABS(s.Total)) as total_sales_value,
                AVG(ABS(s.Price)) as avg_sales_price
            FROM DlySale s
            JOIN Dlyndx ndx ON s.VchCode = ndx.VchCode
            WHERE ndx.VchType = 11  -- Sales invoices
            AND ndx.Draft = 2
            AND ndx.Date BETWEEN %s AND %s
        """
        
        cursor.execute(sql_sales, (start_date, end_date))
        row = cursor.fetchone()
        
        return {
            "sales_orders": int(row['sales_orders'] or 0),
            "total_sales_qty": float(row['total_sales_qty'] or 0),
            "total_sales_value": float(row['total_sales_value'] or 0),
            "avg_sales_price": float(row['avg_sales_price'] or 0)
        }
    
    def _get_inventory_data(self, cursor, year: int, month: int) -> Dict[str, Any]:
        """Get inventory data for the period."""
        
        start_date = f"{year}-{month:02d}-01"
        end_date = f"{year}-{month:02d}-31"
        
        # Get opening inventory (beginning of month)
        sql_opening = """
            SELECT 
                COUNT(DISTINCT p.TypeId) as sku_count,
                SUM(p.Qty) as total_qty,
                SUM(p.Qty * p.Price) as total_value
            FROM Ptype p
            WHERE p.TypeId LIKE '00003%'  -- Finished goods
        """
        
        cursor.execute(sql_opening)
        opening_row = cursor.fetchone()
        
        # Get closing inventory (end of month)
        sql_closing = """
            SELECT 
                COUNT(DISTINCT p.TypeId) as sku_count,
                SUM(p.Qty) as total_qty,
                SUM(p.Qty * p.Price) as total_value
            FROM Ptype p
            WHERE p.TypeId LIKE '00003%'  -- Finished goods
        """
        
        cursor.execute(sql_closing)
        closing_row = cursor.fetchone()
        
        return {
            "opening_sku_count": int(opening_row['sku_count'] or 0),
            "opening_total_qty": float(opening_row['total_qty'] or 0),
            "opening_total_value": float(opening_row['total_value'] or 0),
            "closing_sku_count": int(closing_row['sku_count'] or 0),
            "closing_total_qty": float(closing_row['total_qty'] or 0),
            "closing_total_value": float(closing_row['total_value'] or 0)
        }
    
    def _calculate_analysis(self, production_data: Dict[str, Any], 
                           sales_data: Dict[str, Any], 
                           inventory_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate production-sales-inventory analysis metrics."""
        
        # Calculate key ratios
        production_to_sales_ratio = (production_data['total_production_qty'] / sales_data['total_sales_qty']) if sales_data['total_sales_qty'] > 0 else 0
        inventory_turnover = (sales_data['total_sales_value'] / ((inventory_data['opening_total_value'] + inventory_data['closing_total_value']) / 2)) if inventory_data['opening_total_value'] > 0 else 0
        
        # Calculate inventory changes
        inventory_qty_change = inventory_data['closing_total_qty'] - inventory_data['opening_total_qty']
        inventory_value_change = inventory_data['closing_total_value'] - inventory_data['opening_total_value']
        
        return {
            "production_to_sales_ratio": production_to_sales_ratio,
            "inventory_turnover": inventory_turnover,
            "inventory_qty_change": inventory_qty_change,
            "inventory_value_change": inventory_value_change,
            "production_coverage_days": (inventory_data['closing_total_qty'] / sales_data['total_sales_qty'] * 30) if sales_data['total_sales_qty'] > 0 else 0,
            "sales_growth_potential": "High" if inventory_data['closing_total_qty'] > sales_data['total_sales_qty'] * 1.2 else "Normal"
        }

hr_service = HRService()
inventory_analysis_service = InventoryAnalysisService()