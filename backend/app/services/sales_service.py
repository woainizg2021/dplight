from typing import Dict, Any, Optional, List
from datetime import datetime, date
from app.db.mssql import get_db_connection
from app.db.mysql import get_mysql_connection
from app.models.schemas import SalesOverview
import logging

logger = logging.getLogger(__name__)

class SalesService:
    def get_sales_overview(self, company_key: str, year: int, month: int) -> SalesOverview:
        """
        Get comprehensive sales overview including SKU analysis, channel analysis,
        and month comparison for a specific company.
        """
        try:
            # Get MSSQL connection for sales data
            conn = get_db_connection(company_key)
            
            with conn.cursor(as_dict=True) as cursor:
                # 1. Sales by SKU
                by_sku = self._get_sales_by_sku(cursor, year, month)
                
                # 2. Sales by Channel
                by_channel = self._get_sales_by_channel(cursor, year, month)
                
                # 3. Month Comparison
                month_comparison = self._get_month_comparison(cursor, year, month)
                
                return SalesOverview(
                    company_key=company_key,
                    by_sku=by_sku,
                    by_channel=by_channel,
                    month_comparison=month_comparison
                )
                
        except Exception as e:
            logger.error(f"Error fetching sales overview for {company_key}: {e}")
            raise e
        finally:
            if 'conn' in locals():
                conn.close()
    
    def _get_sales_by_sku(self, cursor, year: int, month: int) -> List[Dict[str, Any]]:
        """Get sales data grouped by SKU/product."""
        
        start_date = f"{year}-{month:02d}-01"
        end_date = f"{year}-{month:02d}-31"
        
        # Get top selling SKUs
        sql_sku = """
            SELECT TOP 20
                CAST(p.FullName AS NVARCHAR(200)) as product_name,
                CAST(p.UserCode AS NVARCHAR(50)) as product_code,
                SUM(ABS(s.Qty)) as total_quantity,
                SUM(ABS(s.Total)) as total_amount,
                AVG(ABS(s.Price)) as avg_price,
                COUNT(DISTINCT s.VchCode) as transaction_count
            FROM DlySale s
            JOIN Dlyndx d ON s.VchCode = d.VchCode
            JOIN Ptype p ON s.PtypeId = p.TypeId
            WHERE d.VchType = 11 
            AND d.Draft = 2
            AND d.Date BETWEEN %s AND %s
            GROUP BY p.FullName, p.UserCode
            ORDER BY total_amount DESC
        """
        
        cursor.execute(sql_sku, (start_date, end_date))
        rows = cursor.fetchall()
        
        sku_data = []
        for row in rows:
            sku_data.append({
                "product_name": row['product_name'],
                "product_code": row['product_code'],
                "quantity": float(row['total_quantity']),
                "amount": float(row['total_amount']),
                "avg_price": float(row['avg_price']),
                "transactions": int(row['transaction_count']),
                "avg_transaction_value": float(row['total_amount']) / int(row['transaction_count'])
            })
        
        return sku_data
    
    def _get_sales_by_channel(self, cursor, year: int, month: int) -> List[Dict[str, Any]]:
        """Get sales data grouped by sales channel/customer type."""
        
        start_date = f"{year}-{month:02d}-01"
        end_date = f"{year}-{month:02d}-31"
        
        # Get sales by customer type (using Btype classification)
        sql_channel = """
            SELECT 
                CASE 
                    WHEN b.TypeId LIKE '00003%' THEN '门市客户'
                    WHEN b.TypeId LIKE '00004%' THEN '经销商'
                    WHEN b.TypeId LIKE '00005%' THEN '工程项目'
                    WHEN b.TypeId LIKE '00006%' THEN '出口客户'
                    ELSE '其他客户'
                END as channel_name,
                COUNT(DISTINCT d.VchCode) as customer_count,
                SUM(ABS(s.Total)) as total_amount,
                SUM(ABS(s.Qty)) as total_quantity,
                AVG(ABS(s.Total)) as avg_order_value
            FROM DlySale s
            JOIN Dlyndx d ON s.VchCode = d.VchCode
            LEFT JOIN Btype b ON d.BtypeId = b.TypeId
            WHERE d.VchType = 11 
            AND d.Draft = 2
            AND d.Date BETWEEN %s AND %s
            GROUP BY 
                CASE 
                    WHEN b.TypeId LIKE '00003%' THEN '门市客户'
                    WHEN b.TypeId LIKE '00004%' THEN '经销商'
                    WHEN b.TypeId LIKE '00005%' THEN '工程项目'
                    WHEN b.TypeId LIKE '00006%' THEN '出口客户'
                    ELSE '其他客户'
                END
            ORDER BY total_amount DESC
        """
        
        cursor.execute(sql_channel, (start_date, end_date))
        rows = cursor.fetchall()
        
        channel_data = []
        for row in rows:
            channel_data.append({
                "channel_name": row['channel_name'],
                "customer_count": int(row['customer_count']),
                "total_amount": float(row['total_amount']),
                "total_quantity": float(row['total_quantity']),
                "avg_order_value": float(row['avg_order_value']),
                "market_share": 0  # Will be calculated later
            })
        
        # Calculate market share
        total_amount = sum(channel['total_amount'] for channel in channel_data)
        for channel in channel_data:
            channel['market_share'] = channel['total_amount'] / total_amount if total_amount > 0 else 0
        
        return channel_data
    
    def _get_month_comparison(self, cursor, year: int, month: int) -> Dict[str, Any]:
        """Get sales comparison between current month and previous month."""
        
        # Current month
        current_start = f"{year}-{month:02d}-01"
        current_end = f"{year}-{month:02d}-31"
        
        # Previous month
        if month == 1:
            prev_year = year - 1
            prev_month = 12
        else:
            prev_year = year
            prev_month = month - 1
        
        prev_start = f"{prev_year}-{prev_month:02d}-01"
        prev_end = f"{prev_year}-{prev_month:02d}-31"
        
        # Get current month totals
        sql_current = """
            SELECT 
                COUNT(DISTINCT d.VchCode) as transaction_count,
                SUM(ABS(s.Total)) as total_amount,
                SUM(ABS(s.Qty)) as total_quantity,
                AVG(ABS(s.Total)) as avg_order_value
            FROM DlySale s
            JOIN Dlyndx d ON s.VchCode = d.VchCode
            WHERE d.VchType = 11 
            AND d.Draft = 2
            AND d.Date BETWEEN %s AND %s
        """
        
        cursor.execute(sql_current, (current_start, current_end))
        current_data = cursor.fetchone()
        
        # Get previous month totals
        cursor.execute(sql_current, (prev_start, prev_end))
        previous_data = cursor.fetchone()
        
        # Calculate growth rates
        current_amount = float(current_data['total_amount'] or 0)
        previous_amount = float(previous_data['total_amount'] or 0)
        amount_growth = (current_amount - previous_amount) / previous_amount if previous_amount > 0 else 0
        
        current_qty = float(current_data['total_quantity'] or 0)
        previous_qty = float(previous_data['total_quantity'] or 0)
        quantity_growth = (current_qty - previous_qty) / previous_qty if previous_qty > 0 else 0
        
        current_transactions = int(current_data['transaction_count'] or 0)
        previous_transactions = int(previous_data['transaction_count'] or 0)
        transaction_growth = (current_transactions - previous_transactions) / previous_transactions if previous_transactions > 0 else 0
        
        return {
            "current_month": {
                "amount": current_amount,
                "quantity": current_qty,
                "transactions": current_transactions,
                "avg_order_value": float(current_data['avg_order_value'] or 0)
            },
            "previous_month": {
                "amount": previous_amount,
                "quantity": previous_qty,
                "transactions": previous_transactions,
                "avg_order_value": float(previous_data['avg_order_value'] or 0)
            },
            "growth_rates": {
                "amount": amount_growth,
                "quantity": quantity_growth,
                "transactions": transaction_growth
            }
        }

sales_service = SalesService()