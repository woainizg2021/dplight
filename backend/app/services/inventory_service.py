from typing import Dict, Any, Optional, List
from datetime import datetime, date
from backend.app.db.mssql import get_db_connection
from backend.app.db.mysql import get_mysql_connection
from backend.app.models.schemas import InventoryReport
import logging

logger = logging.getLogger(__name__)

class InventoryService:
    def get_inventory_report(self, company_key: str, year: int, month: int) -> InventoryReport:
        """
        Get comprehensive inventory report including raw materials, semi-finished goods,
        and finished goods with opening, movements, closing, safety stock, and alerts.
        """
        try:
            # Get MSSQL connection for inventory data
            conn = get_db_connection(company_key)
            
            with conn.cursor(as_dict=True) as cursor:
                # 1. Raw Materials Inventory
                raw_materials = self._get_raw_materials_inventory(cursor, year, month)
                
                # 2. Semi-finished Goods Inventory
                semi_finished = self._get_semi_finished_inventory(cursor, year, month)
                
                # 3. Finished Goods Inventory
                finished_goods = self._get_finished_goods_inventory(cursor, year, month)
                
                # 4. Overall Summary
                summary = self._get_inventory_summary(raw_materials, semi_finished, finished_goods)
                
                return InventoryReport(
                    company_key=company_key,
                    raw_materials=raw_materials,
                    semi_finished=semi_finished,
                    finished_goods=finished_goods,
                    summary=summary
                )
                
        except Exception as e:
            logger.error(f"Error fetching inventory report for {company_key}: {e}")
            raise e
        finally:
            if 'conn' in locals():
                conn.close()
    
    def get_raw_materials(self, company_key: str, year: int, month: int) -> List[Dict[str, Any]]:
        """Get raw materials inventory only."""
        try:
            conn = get_db_connection(company_key)
            with conn.cursor(as_dict=True) as cursor:
                return self._get_raw_materials_inventory(cursor, year, month)
        except Exception as e:
            logger.error(f"Error fetching raw materials for {company_key}: {e}")
            raise e
        finally:
            if 'conn' in locals():
                conn.close()

    def get_finished_goods(self, company_key: str, year: int, month: int) -> List[Dict[str, Any]]:
        """Get finished goods inventory only."""
        try:
            conn = get_db_connection(company_key)
            with conn.cursor(as_dict=True) as cursor:
                return self._get_finished_goods_inventory(cursor, year, month)
        except Exception as e:
            logger.error(f"Error fetching finished goods for {company_key}: {e}")
            raise e
        finally:
            if 'conn' in locals():
                conn.close()

    def _get_raw_materials_inventory(self, cursor, year: int, month: int) -> List[Dict[str, Any]]:
        """Get raw materials inventory data."""
        
        # Get start and end dates for the month
        start_date = f"{year}-{month:02d}-01"
        end_date = f"{year}-{month:02d}-31"
        
        # Get raw materials (category codes starting with 00001, 00002, etc.)
        sql_raw_materials = """
            SELECT 
                p.FullName as product_name,
                p.UserCode as product_code,
                p.TypeId as product_id,
                w.FullName as warehouse_name,
                
                -- Opening balance
                ISNULL((
                    SELECT SUM(Qty) 
                    FROM KfZtr 
                    WHERE PtypeId = p.TypeId 
                    AND WareId = w.TypeId 
                    AND Date < %s
                ), 0) as opening_quantity,
                
                -- Current month receipts
                ISNULL((
                    SELECT SUM(Qty) 
                    FROM KfZtr 
                    WHERE PtypeId = p.TypeId 
                    AND WareId = w.TypeId 
                    AND Date BETWEEN %s AND %s
                    AND VchType IN (1, 11) -- Purchase, Sales Return
                ), 0) as month_in,
                
                -- Current month issues
                ISNULL(ABS((
                    SELECT SUM(Qty) 
                    FROM KfZtr 
                    WHERE PtypeId = p.TypeId 
                    AND WareId = w.TypeId 
                    AND Date BETWEEN %s AND %s
                    AND VchType IN (11, 12) -- Sales, Purchase Return
                )), 0) as month_out,
                
                -- Closing balance
                ISNULL((
                    SELECT SUM(Qty) 
                    FROM KfZtr 
                    WHERE PtypeId = p.TypeId 
                    AND WareId = w.TypeId 
                ), 0) as closing_quantity,
                
                -- Safety stock (from product master)
                ISNULL(p.SafeQty, 0) as safety_stock,
                
                -- Unit cost
                ISNULL(p.Price, 0) as unit_cost
                
            FROM Ptype p
            CROSS JOIN Warehouse w
            WHERE (
                p.TypeId LIKE '00001%' OR -- Raw materials
                p.TypeId LIKE '00002%' OR -- Semi-finished (also raw)
                p.TypeId LIKE '00004%' OR -- Accessories
                p.TypeId LIKE '00005%' OR -- Molds
                p.TypeId LIKE '00007%' OR -- Machines
                p.TypeId LIKE '00009%' OR -- Other accessories
                p.TypeId LIKE '00010%' OR -- Screws
                p.TypeId LIKE '00011%' OR -- Light boards
                p.TypeId LIKE '00012%' OR -- Driver boards
                p.TypeId LIKE '00013%' OR -- Other parts
                p.TypeId LIKE '00127%'    -- Others
            )
            AND p.FullName NOT LIKE '%成品%'
            AND w.FullName LIKE '%原料%'
            HAVING closing_quantity > 0
            ORDER BY closing_quantity DESC
        """
        
        cursor.execute(sql_raw_materials, (start_date, start_date, end_date, start_date, end_date))
        rows = cursor.fetchall()
        
        raw_materials = []
        for row in rows:
            # Calculate stock status
            closing_qty = float(row['closing_quantity'])
            safety_qty = float(row['safety_stock'])
            
            if closing_qty <= 0:
                status = "缺货"
            elif closing_qty < safety_qty:
                status = "库存不足"
            else:
                status = "正常"
            
            # Calculate stock value
            stock_value = closing_qty * float(row['unit_cost'])
            
            raw_materials.append({
                "product_name": row['product_name'],
                "product_code": row['product_code'],
                "warehouse": row['warehouse_name'],
                "opening_quantity": float(row['opening_quantity']),
                "month_in": float(row['month_in']),
                "month_out": float(row['month_out']),
                "closing_quantity": closing_qty,
                "safety_stock": safety_qty,
                "unit_cost": float(row['unit_cost']),
                "stock_value": stock_value,
                "status": status,
                "days_of_stock": 0  # Will be calculated later
            })
        
        return raw_materials
    
    def _get_semi_finished_inventory(self, cursor, year: int, month: int) -> List[Dict[str, Any]]:
        """Get semi-finished goods inventory data."""
        
        start_date = f"{year}-{month:02d}-01"
        end_date = f"{year}-{month:02d}-31"
        
        # Semi-finished goods (category codes starting with 00002)
        sql_semi_finished = """
            SELECT 
                p.FullName as product_name,
                p.UserCode as product_code,
                p.TypeId as product_id,
                w.FullName as warehouse_name,
                
                -- Opening balance
                ISNULL((
                    SELECT SUM(Qty) 
                    FROM KfZtr 
                    WHERE PtypeId = p.TypeId 
                    AND WareId = w.TypeId 
                    AND Date < %s
                ), 0) as opening_quantity,
                
                -- Current month receipts (production completion)
                ISNULL((
                    SELECT SUM(Qty) 
                    FROM KfZtr 
                    WHERE PtypeId = p.TypeId 
                    AND WareId = w.TypeId 
                    AND Date BETWEEN %s AND %s
                    AND VchType IN (174) -- Production completion
                ), 0) as month_in,
                
                -- Current month issues (to production)
                ISNULL(ABS((
                    SELECT SUM(Qty) 
                    FROM KfZtr 
                    WHERE PtypeId = p.TypeId 
                    AND WareId = w.TypeId 
                    AND Date BETWEEN %s AND %s
                    AND VchType IN (171) -- Production issue
                )), 0) as month_out,
                
                -- Closing balance
                ISNULL((
                    SELECT SUM(Qty) 
                    FROM KfZtr 
                    WHERE PtypeId = p.TypeId 
                    AND WareId = w.TypeId 
                ), 0) as closing_quantity,
                
                -- Safety stock
                ISNULL(p.SafeQty, 0) as safety_stock,
                
                -- Unit cost
                ISNULL(p.Price, 0) as unit_cost
                
            FROM Ptype p
            CROSS JOIN Warehouse w
            WHERE p.TypeId LIKE '00002%' -- Semi-finished goods
            AND w.FullName LIKE '%半成品%'
            HAVING closing_quantity > 0
            ORDER BY closing_quantity DESC
        """
        
        cursor.execute(sql_semi_finished, (start_date, start_date, end_date, start_date, end_date))
        rows = cursor.fetchall()
        
        semi_finished = []
        for row in rows:
            closing_qty = float(row['closing_quantity'])
            safety_qty = float(row['safety_stock'])
            
            if closing_qty <= 0:
                status = "缺货"
            elif closing_qty < safety_qty:
                status = "库存不足"
            else:
                status = "正常"
            
            stock_value = closing_qty * float(row['unit_cost'])
            
            semi_finished.append({
                "product_name": row['product_name'],
                "product_code": row['product_code'],
                "warehouse": row['warehouse_name'],
                "opening_quantity": float(row['opening_quantity']),
                "month_in": float(row['month_in']),
                "month_out": float(row['month_out']),
                "closing_quantity": closing_qty,
                "safety_stock": safety_qty,
                "unit_cost": float(row['unit_cost']),
                "stock_value": stock_value,
                "status": status,
                "days_of_stock": 0
            })
        
        return semi_finished
    
    def _get_finished_goods_inventory(self, cursor, year: int, month: int) -> List[Dict[str, Any]]:
        """Get finished goods inventory data."""
        
        start_date = f"{year}-{month:02d}-01"
        end_date = f"{year}-{month:02d}-31"
        
        # Finished goods (category codes starting with 00003)
        sql_finished_goods = """
            SELECT 
                p.FullName as product_name,
                p.UserCode as product_code,
                p.TypeId as product_id,
                w.FullName as warehouse_name,
                
                -- Opening balance
                ISNULL((
                    SELECT SUM(Qty) 
                    FROM KfZtr 
                    WHERE PtypeId = p.TypeId 
                    AND WareId = w.TypeId 
                    AND Date < %s
                ), 0) as opening_quantity,
                
                -- Current month receipts (production completion)
                ISNULL((
                    SELECT SUM(Qty) 
                    FROM KfZtr 
                    WHERE PtypeId = p.TypeId 
                    AND WareId = w.TypeId 
                    AND Date BETWEEN %s AND %s
                    AND VchType IN (174) -- Production completion
                ), 0) as month_in,
                
                -- Current month issues (sales)
                ISNULL(ABS((
                    SELECT SUM(Qty) 
                    FROM KfZtr 
                    WHERE PtypeId = p.TypeId 
                    AND WareId = w.TypeId 
                    AND Date BETWEEN %s AND %s
                    AND VchType IN (11) -- Sales
                )), 0) as month_out,
                
                -- Closing balance
                ISNULL((
                    SELECT SUM(Qty) 
                    FROM KfZtr 
                    WHERE PtypeId = p.TypeId 
                    AND WareId = w.TypeId 
                ), 0) as closing_quantity,
                
                -- Safety stock
                ISNULL(p.SafeQty, 0) as safety_stock,
                
                -- Unit cost
                ISNULL(p.Price, 0) as unit_cost
                
            FROM Ptype p
            CROSS JOIN Warehouse w
            WHERE p.TypeId LIKE '00003%' -- Finished goods
            AND w.FullName LIKE '%成品%'
            HAVING closing_quantity > 0
            ORDER BY closing_quantity DESC
        """
        
        cursor.execute(sql_finished_goods, (start_date, start_date, end_date, start_date, end_date))
        rows = cursor.fetchall()
        
        finished_goods = []
        for row in rows:
            closing_qty = float(row['closing_quantity'])
            safety_qty = float(row['safety_stock'])
            
            if closing_qty <= 0:
                status = "缺货"
            elif closing_qty < safety_qty:
                status = "库存不足"
            else:
                status = "正常"
            
            stock_value = closing_qty * float(row['unit_cost'])
            
            finished_goods.append({
                "product_name": row['product_name'],
                "product_code": row['product_code'],
                "warehouse": row['warehouse_name'],
                "opening_quantity": float(row['opening_quantity']),
                "month_in": float(row['month_in']),
                "month_out": float(row['month_out']),
                "closing_quantity": closing_qty,
                "safety_stock": safety_qty,
                "unit_cost": float(row['unit_cost']),
                "stock_value": stock_value,
                "status": status,
                "days_of_stock": 0
            })
        
        return finished_goods
    
    def _get_inventory_summary(self, raw_materials: List[Dict], semi_finished: List[Dict], finished_goods: List[Dict]) -> Dict[str, Any]:
        """Calculate overall inventory summary."""
        
        # Calculate totals for each category
        raw_materials_value = sum(item['stock_value'] for item in raw_materials)
        semi_finished_value = sum(item['stock_value'] for item in semi_finished)
        finished_goods_value = sum(item['stock_value'] for item in finished_goods)
        
        total_value = raw_materials_value + semi_finished_value + finished_goods_value
        
        # Count items with different statuses
        raw_low_stock = sum(1 for item in raw_materials if item['status'] == '库存不足')
        raw_out_of_stock = sum(1 for item in raw_materials if item['status'] == '缺货')
        
        semi_low_stock = sum(1 for item in semi_finished if item['status'] == '库存不足')
        semi_out_of_stock = sum(1 for item in semi_finished if item['status'] == '缺货')
        
        finished_low_stock = sum(1 for item in finished_goods if item['status'] == '库存不足')
        finished_out_of_stock = sum(1 for item in finished_goods if item['status'] == '缺货')
        
        return {
            "total_value": total_value,
            "raw_materials_value": raw_materials_value,
            "semi_finished_value": semi_finished_value,
            "finished_goods_value": finished_goods_value,
            "raw_materials_count": len(raw_materials),
            "semi_finished_count": len(semi_finished),
            "finished_goods_count": len(finished_goods),
            "low_stock_items": raw_low_stock + semi_low_stock + finished_low_stock,
            "out_of_stock_items": raw_out_of_stock + semi_out_of_stock + finished_out_of_stock,
            "total_items": len(raw_materials) + len(semi_finished) + len(finished_goods)
        }

inventory_service = InventoryService()