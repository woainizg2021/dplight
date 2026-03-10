from typing import Dict, Any, Optional, List
from datetime import datetime, date
from backend.app.db.mssql import get_db_connection
from backend.app.db.mysql import get_mysql_connection
from backend.app.models.schemas import SalesToday, SalesTrend, CustomerRanking, ProductRanking
import logging

logger = logging.getLogger(__name__)

class SalesTodayService:
    """
    Service for today's sales data and analysis migrated from Streamlit sales_today.py module.
    This service provides comprehensive sales reporting with AI analysis capabilities.
    """
    
    def get_sales_today(self, company_key: str) -> SalesToday:
        """
        Get comprehensive today's sales data with detailed analysis.
        Migrated from sales_today.py Streamlit module.
        """
        try:
            conn = get_db_connection(company_key)
            
            with conn.cursor(as_dict=True) as cursor:
                today = datetime.now().date()
                
                # Get today's sales summary
                today_sales = self._get_today_sales_summary(cursor, today)
                
                # Get sales trends
                sales_trends = self._get_sales_trends(cursor, today)
                
                # Get customer rankings
                customer_rankings = self._get_customer_rankings(cursor, today)
                
                # Get product rankings
                product_rankings = self._get_product_rankings(cursor, today)
                
                # Get sales performance vs targets
                performance_vs_target = self._get_performance_vs_target(cursor, today)
                
                return SalesToday(
                    company_key=company_key,
                    report_date=today.isoformat(),
                    sales_summary=today_sales,
                    sales_trends=sales_trends,
                    customer_rankings=customer_rankings,
                    product_rankings=product_rankings,
                    performance_vs_target=performance_vs_target
                )
                
        except Exception as e:
            logger.error(f"Error fetching today's sales for {company_key}: {e}")
            raise e
        finally:
            if 'conn' in locals():
                conn.close()
    
    def _get_today_sales_summary(self, cursor, today: date) -> Dict[str, Any]:
        """Get today's sales summary statistics."""
        
        sql_summary = """
            SELECT 
                COUNT(DISTINCT s.VchCode) as invoice_count,
                COUNT(DISTINCT s.BtypeId) as customer_count,
                SUM(ABS(s.Qty)) as total_quantity,
                SUM(ABS(s.Total)) as total_amount,
                AVG(ABS(s.Price)) as avg_price,
                MAX(s.Date) as last_sale_time
            FROM DlySale s
            JOIN Dlyndx d ON s.VchCode = d.VchCode
            WHERE d.VchType = 11 
            AND d.Draft = 2
            AND CAST(d.Date AS DATE) = %s
        """
        
        cursor.execute(sql_summary, (today,))
        row = cursor.fetchone()
        
        return {
            "invoice_count": int(row['invoice_count'] or 0),
            "customer_count": int(row['customer_count'] or 0),
            "total_quantity": float(row['total_quantity'] or 0),
            "total_amount": float(row['total_amount'] or 0),
            "avg_price": float(row['avg_price'] or 0),
            "last_sale_time": row['last_sale_time'].strftime('%H:%M:%S') if row['last_sale_time'] else '',
            "vs_yesterday": self._get_vs_yesterday_comparison(cursor, today)
        }
    
    def _get_vs_yesterday_comparison(self, cursor, today: date) -> Dict[str, Any]:
        """Get comparison with yesterday's sales."""
        
        yesterday = today - timedelta(days=1)
        
        # Get yesterday's sales
        sql_yesterday = """
            SELECT 
                COUNT(DISTINCT s.VchCode) as invoice_count,
                SUM(ABS(s.Qty)) as total_quantity,
                SUM(ABS(s.Total)) as total_amount
            FROM DlySale s
            JOIN Dlyndx d ON s.VchCode = d.VchCode
            WHERE d.VchType = 11 
            AND d.Draft = 2
            AND CAST(d.Date AS DATE) = %s
        """
        
        cursor.execute(sql_yesterday, (yesterday,))
        yesterday_row = cursor.fetchone()
        
        # Get today's sales (already calculated)
        cursor.execute(sql_yesterday.replace("%s", "CAST(GETDATE() AS DATE)"))
        today_row = cursor.fetchone()
        
        yesterday_amount = float(yesterday_row['total_amount'] or 0)
        today_amount = float(today_row['total_amount'] or 0)
        
        return {
            "amount_change": today_amount - yesterday_amount,
            "amount_change_pct": ((today_amount - yesterday_amount) / yesterday_amount * 100) if yesterday_amount > 0 else 0,
            "quantity_change": float(today_row['total_quantity'] or 0) - float(yesterday_row['total_quantity'] or 0),
            "invoice_change": int(today_row['invoice_count'] or 0) - int(yesterday_row['invoice_count'] or 0)
        }
    
    def _get_sales_trends(self, cursor, today: date) -> SalesTrend:
        """Get sales trends for the past 7 days."""
        
        sql_trends = """
            SELECT 
                CAST(d.Date AS DATE) as sale_date,
                COUNT(DISTINCT s.VchCode) as invoice_count,
                SUM(ABS(s.Qty)) as total_quantity,
                SUM(ABS(s.Total)) as total_amount,
                AVG(ABS(s.Price)) as avg_price
            FROM DlySale s
            JOIN Dlyndx d ON s.VchCode = d.VchCode
            WHERE d.VchType = 11 
            AND d.Draft = 2
            AND CAST(d.Date AS DATE) >= DATEADD(day, -6, CAST(GETDATE() AS DATE))
            GROUP BY CAST(d.Date AS DATE)
            ORDER BY sale_date DESC
        """
        
        cursor.execute(sql_trends)
        rows = cursor.fetchall()
        
        trend_data = []
        for row in rows:
            trend_data.append({
                "date": row['sale_date'].strftime('%Y-%m-%d') if row['sale_date'] else '',
                "invoice_count": int(row['invoice_count'] or 0),
                "total_quantity": float(row['total_quantity'] or 0),
                "total_amount": float(row['total_amount'] or 0),
                "avg_price": float(row['avg_price'] or 0)
            })
        
        return SalesTrend(
            period_days=7,
            trend_data=trend_data,
            avg_daily_amount=sum(t['total_amount'] for t in trend_data) / len(trend_data) if trend_data else 0,
            trend_direction=self._calculate_trend_direction(trend_data)
        )
    
    def _get_customer_rankings(self, cursor, today: date) -> List[CustomerRanking]:
        """Get today's top customers by sales amount."""
        
        sql_customers = """
            SELECT TOP 10
                b.FullName as customer_name,
                b.UserCode as customer_code,
                COUNT(DISTINCT s.VchCode) as invoice_count,
                SUM(ABS(s.Qty)) as total_quantity,
                SUM(ABS(s.Total)) as total_amount,
                AVG(ABS(s.Price)) as avg_price,
                MAX(s.Date) as last_purchase_date
            FROM DlySale s
            JOIN Dlyndx d ON s.VchCode = d.VchCode
            JOIN Btype b ON s.BtypeId = b.TypeId
            WHERE d.VchType = 11 
            AND d.Draft = 2
            AND CAST(d.Date AS DATE) = %s
            GROUP BY b.FullName, b.UserCode
            ORDER BY total_amount DESC
        """
        
        cursor.execute(sql_customers, (today,))
        rows = cursor.fetchall()
        
        customers = []
        for i, row in enumerate(rows, 1):
            customers.append({
                "rank": i,
                "customer_name": row['customer_name'],
                "customer_code": row['customer_code'],
                "invoice_count": int(row['invoice_count'] or 0),
                "total_quantity": float(row['total_quantity'] or 0),
                "total_amount": float(row['total_amount'] or 0),
                "avg_price": float(row['avg_price'] or 0),
                "last_purchase_date": row['last_purchase_date'].strftime('%H:%M:%S') if row['last_purchase_date'] else ''
            })
        
        return customers
    
    def _get_product_rankings(self, cursor, today: date) -> List[ProductRanking]:
        """Get today's top products by sales quantity and amount."""
        
        sql_products = """
            SELECT TOP 15
                p.FullName as product_name,
                p.UserCode as product_code,
                COUNT(DISTINCT s.VchCode) as invoice_count,
                SUM(ABS(s.Qty)) as total_quantity,
                SUM(ABS(s.Total)) as total_amount,
                AVG(ABS(s.Price)) as avg_price,
                SUM(ABS(s.Total)) / SUM(ABS(s.Qty)) as avg_unit_price
            FROM DlySale s
            JOIN Dlyndx d ON s.VchCode = d.VchCode
            JOIN Ptype p ON s.PtypeId = p.TypeId
            WHERE d.VchType = 11 
            AND d.Draft = 2
            AND CAST(d.Date AS DATE) = %s
            GROUP BY p.FullName, p.UserCode
            ORDER BY total_amount DESC
        """
        
        cursor.execute(sql_products, (today,))
        rows = cursor.fetchall()
        
        products = []
        for i, row in enumerate(rows, 1):
            products.append({
                "rank": i,
                "product_name": row['product_name'],
                "product_code": row['product_code'],
                "invoice_count": int(row['invoice_count'] or 0),
                "total_quantity": float(row['total_quantity'] or 0),
                "total_amount": float(row['total_amount'] or 0),
                "avg_price": float(row['avg_price'] or 0),
                "avg_unit_price": float(row['avg_unit_price'] or 0)
            })
        
        return products
    
    def _get_performance_vs_target(self, cursor, today: date) -> Dict[str, Any]:
        """Get today's performance vs monthly target."""
        
        current_month = today.strftime('%Y-%m')
        
        # Get monthly target
        sql_target = """
            SELECT 
                monthly_sales_target,
                daily_target
            FROM sales_targets 
            WHERE target_period = %s
        """
        
        cursor.execute(sql_target, (current_month,))
        target_row = cursor.fetchone()
        
        if not target_row:
            return {
                "monthly_target": 0,
                "daily_target": 0,
                "today_actual": 0,
                "month_to_date_actual": 0,
                "daily_completion_rate": 0,
                "monthly_completion_rate": 0
            }
        
        monthly_target = float(target_row['monthly_sales_target'] or 0)
        daily_target = float(target_row['daily_target'] or 0)
        
        # Get today's actual sales
        today_actual = self._get_today_sales_summary(cursor, today)['total_amount']
        
        # Get month-to-date actual sales
        sql_mtd = """
            SELECT 
                SUM(ABS(s.Total)) as mtd_amount
            FROM DlySale s
            JOIN Dlyndx d ON s.VchCode = d.VchCode
            WHERE d.VchType = 11 
            AND d.Draft = 2
            AND FORMAT(d.Date, 'yyyy-MM') = %s
        """
        
        cursor.execute(sql_mtd, (current_month,))
        mtd_row = cursor.fetchone()
        month_to_date_actual = float(mtd_row['mtd_amount'] or 0)
        
        return {
            "monthly_target": monthly_target,
            "daily_target": daily_target,
            "today_actual": today_actual,
            "month_to_date_actual": month_to_date_actual,
            "daily_completion_rate": (today_actual / daily_target * 100) if daily_target > 0 else 0,
            "monthly_completion_rate": (month_to_date_actual / monthly_target * 100) if monthly_target > 0 else 0
        }
    
    def _calculate_trend_direction(self, trend_data: List[Dict[str, Any]]) -> str:
        """Calculate sales trend direction based on recent data."""
        if len(trend_data) < 3:
            return "stable"
        
        recent_amounts = [t['total_amount'] for t in trend_data[:3]]
        
        if all(recent_amounts[i] > recent_amounts[i+1] for i in range(len(recent_amounts)-1)):
            return "increasing"
        elif all(recent_amounts[i] < recent_amounts[i+1] for i in range(len(recent_amounts)-1)):
            return "decreasing"
        else:
            return "stable"
    
    def generate_ai_report(self, company_key: str, sales_data: SalesToday) -> str:
        """
        Generate AI-powered sales analysis report.
        This mimics the AI analysis functionality from the original Streamlit module.
        """
        
        summary = sales_data.sales_summary
        trends = sales_data.sales_trends
        customers = sales_data.customer_rankings[:5]  # Top 5 customers
        products = sales_data.product_rankings[:5]     # Top 5 products
        performance = sales_data.performance_vs_target
        
        # Generate comprehensive analysis
        report = f"""
        <h3>📊 {company_key} 今日销售分析报告</h3>
        
        <h4>📈 销售概况</h4>
        <ul>
        <li>今日销售额: {summary['total_amount']:,.2f}</li>
        <li>销售单据数: {summary['invoice_count']} 单</li>
        <li>客户数量: {summary['customer_count']} 家</li>
        <li>平均单价: {summary['avg_price']:,.2f}</li>
        </ul>
        
        <h4>📊 同比分析</h4>
        <ul>
        <li>金额变化: {summary['vs_yesterday']['amount_change']:,.2f} ({summary['vs_yesterday']['amount_change_pct']:.1f}%)</li>
        <li>数量变化: {summary['vs_yesterday']['quantity_change']:,.0f}</li>
        <li>单据变化: {summary['vs_yesterday']['invoice_change']} 单</li>
        </ul>
        
        <h4>🎯 目标完成情况</h4>
        <ul>
        <li>日目标完成率: {performance['daily_completion_rate']:.1f}%</li>
        <li>月目标完成率: {performance['monthly_completion_rate']:.1f}%</li>
        <li>今日实际: {performance['today_actual']:,.2f} / {performance['daily_target']:,.2f}</li>
        </ul>
        
        <h4>🏆 重点客户</h4>
        <ul>
        """
        
        for customer in customers:
            report += f"<li>{customer['customer_name']}: {customer['total_amount']:,.2f} ({customer['total_quantity']:,.0f}件)</li>"
        
        report += """
        </ul>
        
        <h4>📦 热销产品</h4>
        <ul>
        """
        
        for product in products:
            report += f"<li>{product['product_name']}: {product['total_quantity']:,.0f}件, {product['total_amount']:,.2f}</li>"
        
        report += """
        </ul>
        
        <h4>📈 趋势分析</h4>
        <ul>
        <li>7日平均日销售额: {trends.avg_daily_amount:,.2f}</li>
        <li>趋势方向: {trends.trend_direction}</li>
        </ul>
        """
        
        return report

sales_today_service = SalesTodayService()