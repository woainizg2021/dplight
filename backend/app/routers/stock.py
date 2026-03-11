from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any, Optional
import pymssql
import logging
import datetime
from app.config import ERP_CREDENTIALS, ERP_HOST, ERP_PORT

router = APIRouter()
logger = logging.getLogger(__name__)

def get_db_connection(tenant_key: str):
    creds = ERP_CREDENTIALS.get(tenant_key)
    if not creds:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    return pymssql.connect(
        server=ERP_HOST,
        port=ERP_PORT,
        user=creds['user'],
        password=creds['pass'],
        database=creds['db'],
        charset='utf8'
    )

@router.get("/days/{tenant_key}")
async def get_stock_days(tenant_key: str, keyword: str = None, status_filter: str = None):
    """
    Get Stock Days (可销天数)
    """
    try:
        conn = get_db_connection(tenant_key)
        cursor = conn.cursor(as_dict=True)
        
        # Determine prefix based on country (logic from stock_days.py)
        # 00002 for UGANDA, 00003 for others
        type_pfx = "00002" if "UGANDA" in tenant_key else "00003"
        
        sql = f"""
            SELECT 
                CAST(v.存货名称 AS NVARCHAR(200)) AS stock_name,
                CAST(v.存货编号 AS VARCHAR(50)) AS stock_code,
                CAST(v.热销否 AS NVARCHAR(50)) AS is_hot,
                CAST(v.下单否 AS NVARCHAR(50)) AS is_order,
                CAST(v.排产否 AS NVARCHAR(50)) AS is_produce,
                v.总可销天数 AS days_available,
                v.总箱数 AS total_boxes,
                v.在途可生产箱数 AS transit_boxes,
                v.在仓可生产箱数 AS warehouse_boxes,
                v.[2025年月均销量] AS avg_monthly_sales,
                v.近90天日均销售箱数 AS avg_daily_sales_90,
                CAST(v.缺货材料 AS NVARCHAR(MAX)) AS missing_materials,
                v.最近入库 AS last_in_date,
                v.最近箱数 AS last_in_boxes,
                v.门市箱数 AS store_boxes,
                v.辽沈箱数 AS factory_boxes
            FROM [v_未来可销天数] v
            INNER JOIN Ptype c ON RTRIM(CAST(v.存货编号 AS NVARCHAR(50))) = RTRIM(CAST(c.UserCode AS NVARCHAR(50)))
            WHERE RTRIM(CAST(c.typeid AS NVARCHAR(50))) LIKE '{type_pfx}%'
            ORDER BY v.[总可销天数] ASC
        """
        
        cursor.execute(sql)
        rows = cursor.fetchall()
        conn.close()
        
        # Client-side filtering (easier than SQL injection risk with dynamic WHEREs)
        results = []
        for row in rows:
            # Filter by keyword
            if keyword:
                kw = keyword.lower()
                if kw not in str(row['stock_name']).lower() and kw not in str(row['stock_code']).lower():
                    continue
            
            # Filter by status
            # status_filter: comma separated "hot,order,produce"
            if status_filter:
                filters = status_filter.split(',')
                keep = True
                if 'hot' in filters and row['is_hot'] not in ['是', 'Yes']: keep = False
                if 'order' in filters and row['is_order'] not in ['下单', 'Order']: keep = False
                if 'produce' in filters and row['is_produce'] not in ['排产', 'Produce']: keep = False
                if not keep: continue
                
            results.append(row)
            
        return results

    except Exception as e:
        logger.error(f"Error fetching stock days for {tenant_key}: {e}")
        # Return empty list or error
        # Some tenants might not have the view
        return []

@router.get("/finished/{tenant_key}")
async def get_stock_finished(
    tenant_key: str, 
    start_date: str, 
    end_date: str, 
    warehouse: str = None,
    keyword: str = None
):
    """
    Get Finished Stock Movement (成品库存变动)
    """
    try:
        conn = get_db_connection(tenant_key)
        cursor = conn.cursor(as_dict=True)
        
        wh_filter = ""
        if warehouse and warehouse != "All":
             wh_filter = f"WHERE CAST([仓库名称] AS NVARCHAR(100)) = N'{warehouse}'"
             
        sql = f"""
        SELECT * FROM (
            SELECT
                CAST([仓库名称] AS NVARCHAR(100)) AS warehouse_name,
                CAST([存货编号] AS NVARCHAR(50)) AS stock_code,
                CAST([存货名称] AS NVARCHAR(200)) AS stock_name,
                SUM(CASE WHEN [单据日期] < '{start_date}' THEN [变动数量] ELSE 0 END) AS qty_start,
                SUM(CASE WHEN [单据日期] < '{start_date}' THEN [变动箱数] ELSE 0 END) AS box_start,
                SUM(CASE WHEN [单据日期] BETWEEN '{start_date}' AND '{end_date}' AND [变动数量] > 0 THEN [变动数量] ELSE 0 END) AS qty_in,
                SUM(CASE WHEN [单据日期] BETWEEN '{start_date}' AND '{end_date}' AND [变动数量] > 0 THEN [变动箱数] ELSE 0 END) AS box_in,
                ABS(SUM(CASE WHEN [单据日期] BETWEEN '{start_date}' AND '{end_date}' AND [变动数量] < 0 THEN [变动数量] ELSE 0 END)) AS qty_out,
                ABS(SUM(CASE WHEN [单据日期] BETWEEN '{start_date}' AND '{end_date}' AND [变动数量] < 0 THEN [变动箱数] ELSE 0 END)) AS box_out,
                SUM(CASE WHEN [单据日期] <= '{end_date}' THEN [变动数量] ELSE 0 END) AS qty_end,
                SUM(CASE WHEN [单据日期] <= '{end_date}' THEN [变动箱数] ELSE 0 END) AS box_end
            FROM [v_成品仓库变动查询]
            {wh_filter}
            GROUP BY [仓库名称], [存货编号], [存货名称]
        ) t
        WHERE t.qty_start <> 0 OR t.qty_in <> 0 OR t.qty_out <> 0 OR t.qty_end <> 0
        ORDER BY t.qty_end DESC
        """
        
        cursor.execute(sql)
        rows = cursor.fetchall()
        conn.close()
        
        results = []
        for row in rows:
            if keyword:
                kw = keyword.lower()
                if kw not in str(row['stock_name']).lower() and kw not in str(row['stock_code']).lower():
                    continue
            results.append(row)
            
        return results
        
    except Exception as e:
        logger.error(f"Error fetching finished stock for {tenant_key}: {e}")
        return []

@router.get("/warehouses/{tenant_key}")
async def get_warehouses(tenant_key: str):
    """
    Get list of finished goods warehouses
    """
    try:
        conn = get_db_connection(tenant_key)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT CAST([仓库名称] AS NVARCHAR(100)) FROM [v_成品仓库变动查询]")
        rows = cursor.fetchall()
        conn.close()
        return [row[0] for row in rows if row[0]]
    except Exception as e:
        logger.error(f"Error fetching warehouses for {tenant_key}: {e}")
        return []
