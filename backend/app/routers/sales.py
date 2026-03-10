from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Dict, Any, Optional
import logging
import datetime
import pymssql
from backend.app.services.db_service import get_db_connection as get_mssql_connection

router = APIRouter()
logger = logging.getLogger(__name__)

# --- Helper Functions ---

def get_db(tenant_key: str):
    """
    Dependency to get MSSQL connection.
    Refactored to use the shared service.
    """
    try:
        conn = get_mssql_connection(tenant_key)
        return conn
    except Exception as e:
        logger.error(f"Failed to connect to DB for {tenant_key}: {e}")
        raise HTTPException(status_code=500, detail=f"Database connection error: {str(e)}")

# --- Endpoints ---

@router.get("/daily/{tenant_key}")
async def get_sales_daily_details(tenant_key: str, date: str = None):
    """
    Get detailed sales transactions for a specific tenant on a specific date.
    Refactored to use shared DB connection.
    """
    if not date:
        date = datetime.date.today().strftime('%Y-%m-%d')
        
    conn = get_db(tenant_key)
    try:
        cursor = conn.cursor(as_dict=True)
        
        # 1. Sales Transactions
        sql_sales = f"""
            SELECT 
                d.VchCode as vch_code, 
                d.Number AS full_number, 
                CAST(ISNULL(d.Summary, '') AS NVARCHAR(500)) AS summary,
                CASE WHEN d.VchType = 11 THEN ABS(d.Total) ELSE 0 END AS amount,
                ISNULL((SELECT SUM(ABS(DebitTotal)) FROM DlyA a WHERE a.VchCode = d.VchCode AND a.AtypeId LIKE '0000100001%'), 0) AS cash,
                ISNULL((SELECT SUM(ABS(DebitTotal)) FROM DlyA a WHERE a.VchCode = d.VchCode AND a.AtypeId LIKE '0000100002%'), 0) AS bank,
                CAST(b.FullName AS NVARCHAR(200)) AS customer_name
            FROM Dlyndx d 
            LEFT JOIN Btype b ON d.BtypeId = b.TypeId
            WHERE d.Date = '{date}' AND d.Draft = 2 AND d.VchType IN (11, 4, 2) 
            ORDER BY d.VchCode DESC
        """
        cursor.execute(sql_sales)
        rows = cursor.fetchall()
        
        transactions = []
        for row in rows:
            amount = float(row['amount'])
            cash = float(row['cash'])
            bank = float(row['bank'])
            receivable = max(0, amount - cash - bank) if amount > 0 else 0
            
            # Extract manual number from summary
            import re
            manual_number = ""
            if row['summary']:
                match = re.search(r'[(（](.*?)[)）]', row['summary'])
                if match:
                    manual_number = match.group(1)
            
            transactions.append({
                "vch_code": row['vch_code'],
                "full_number": row['full_number'],
                "display_number": row['full_number'][-5:] if len(row['full_number']) > 5 else row['full_number'],
                "manual_number": manual_number,
                "summary": row['summary'],
                "amount": amount,
                "cash": cash,
                "bank": bank,
                "receivable": receivable,
                "customer_name": row['customer_name']
            })

        # 2. Expense Details
        expenses = []
        try:
            # Check columns first to decide lendtotal/credit
            cursor.execute("SELECT name FROM sys.columns WHERE object_id = OBJECT_ID('t_cw_dly')")
            cols = [r['name'].lower() for r in cursor.fetchall()]
            
            f_lend = 'lendtotal'
            f_debit = 'debittotal'
            if 'credit' in cols:
                f_lend = 'credit'
                f_debit = 'debit'
            elif 'df' in cols:
                f_lend = 'df'
                f_debit = 'jf'

            sql_exp = f"""
            SELECT 
                RTRIM(a.atypeid) AS account_id, 
                ISNULL(vt.FullName, 'Manual') AS vch_type_name, 
                a.vchtype AS vch_type_code,
                SUM(CASE WHEN a.vchtype = 45 THEN ABS(ISNULL(a.{f_debit}, 0)) ELSE ISNULL(a.{f_lend}, 0) END) AS amount
            FROM t_cw_dly a 
            JOIN t_cw_dlyndx ndx ON a.vchcode = ndx.vchcode 
            LEFT JOIN vchtype vt ON a.vchtype = vt.vchtype
            WHERE a.date = '{date}' 
              AND ndx.draft = 2 
              AND RTRIM(a.atypeid) IN ('000010000100001', '000010000100002', '000010000100003', '000010000100004')
            GROUP BY RTRIM(a.atypeid), ISNULL(vt.FullName, 'Manual'), a.vchtype
            """
            cursor.execute(sql_exp)
            expenses_raw = cursor.fetchall()
            
            acc_map = {
                '000010000100001': '门市先令现金', 
                '000010000100002': '工厂先令现金', 
                '000010000100003': '门市美金现金', 
                '000010000100004': '工厂美金现金'
            }
            
            # Aggregate
            exp_summary = {}
            for aid, name in acc_map.items():
                exp_summary[name] = {'name': name, 'fee': 0.0, 'payment': 0.0, 'return': 0.0, 'other': 0.0, 'total': 0.0}

            for row in expenses_raw:
                aid = row['account_id']
                if aid not in acc_map: continue
                
                name = acc_map[aid]
                amt = float(row['amount'])
                vname = row['vch_type_name']
                vcode = str(row['vch_type_code'])
                
                if vcode == '45' or '退货' in vname: exp_summary[name]['return'] += amt
                elif '付款' in vname: exp_summary[name]['payment'] += amt
                elif '费用' in vname or '凭证' in vname: exp_summary[name]['fee'] += amt
                else: exp_summary[name]['other'] += amt
                
                exp_summary[name]['total'] += amt
            
            expenses = list(exp_summary.values())
            
        except Exception as e:
            logger.error(f"Expense query error: {e}")
            
        conn.close()
        
        return {
            "transactions": transactions,
            "expenses": expenses,
            "tenant": tenant_key,
            "date": date
        }
        
    except Exception as e:
        if conn: conn.close()
        logger.error(f"Error fetching daily details for {tenant_key}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/details/{tenant_key}")
async def get_sales_details(
    tenant_key: str, 
    start_date: str, 
    end_date: str,
    customer_name: str = Query(None),
    product_name: str = Query(None),
    page: int = 1,
    page_size: int = 20
):
    """
    Get sales detail records with filtering and pagination.
    """
    conn = get_db(tenant_key)
    try:
        cursor = conn.cursor(as_dict=True)
        
        # Base filters
        where_clause = f"d.Date BETWEEN '{start_date}' AND '{end_date}' AND d.Draft = 2 AND d.VchType = 11"
        if customer_name:
            where_clause += f" AND b.FullName LIKE N'%{customer_name}%'"
        if product_name:
            where_clause += f" AND p.FullName LIKE N'%{product_name}%'"
            
        # Count total
        count_sql = f"""
            SELECT COUNT(*) as total
            FROM DlySale t
            JOIN Dlyndx d ON t.VchCode = d.VchCode
            LEFT JOIN Ptype p ON t.PtypeId = p.TypeId
            LEFT JOIN Btype b ON d.BtypeId = b.TypeId
            WHERE {where_clause}
        """
        cursor.execute(count_sql)
        total_rows = cursor.fetchone()['total']
        
        # Query Data
        offset = (page - 1) * page_size
        sql = f"""
            SELECT 
                CONVERT(varchar(10), d.Date, 120) as date,
                d.Number as bill_no,
                CAST(b.FullName AS NVARCHAR(200)) as customer_name,
                CAST(p.FullName AS NVARCHAR(200)) as product_name,
                CAST(p.Standard AS NVARCHAR(200)) as standard,
                ABS(t.Qty) as qty,
                ABS(t.Price) as price,
                ABS(t.Total) as amount,
                CAST(d.Summary AS NVARCHAR(500)) as summary
            FROM DlySale t
            JOIN Dlyndx d ON t.VchCode = d.VchCode
            LEFT JOIN Ptype p ON t.PtypeId = p.TypeId
            LEFT JOIN Btype b ON d.BtypeId = b.TypeId
            WHERE {where_clause}
            ORDER BY d.Date DESC, d.VchCode DESC
            OFFSET {offset} ROWS FETCH NEXT {page_size} ROWS ONLY
        """
        cursor.execute(sql)
        rows = cursor.fetchall()
        
        return {
            "items": rows,
            "total": total_rows,
            "page": page,
            "page_size": page_size
        }
    except Exception as e:
        logger.error(f"Error fetching sales details: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn: conn.close()


@router.get("/ranking/customer/{tenant_key}")
async def get_customer_ranking(
    tenant_key: str,
    start_date: str,
    end_date: str,
    limit: int = 20
):
    """
    Get top customers by sales amount.
    """
    conn = get_db(tenant_key)
    try:
        cursor = conn.cursor(as_dict=True)
        
        sql = f"""
            SELECT TOP {limit}
                CAST(b.FullName AS NVARCHAR(200)) as name,
                SUM(ABS(t.Total)) as value
            FROM DlySale t
            JOIN Dlyndx d ON t.VchCode = d.VchCode
            LEFT JOIN Btype b ON d.BtypeId = b.TypeId
            WHERE d.Date BETWEEN '{start_date}' AND '{end_date}' 
              AND d.Draft = 2 
              AND d.VchType = 11
            GROUP BY b.FullName
            ORDER BY value DESC
        """
        cursor.execute(sql)
        rows = cursor.fetchall()
        return rows
    except Exception as e:
        logger.error(f"Error fetching customer ranking: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn: conn.close()


@router.get("/ranking/sku/{tenant_key}")
async def get_sku_ranking(
    tenant_key: str,
    start_date: str,
    end_date: str,
    limit: int = 20
):
    """
    Get top products by quantity.
    """
    conn = get_db(tenant_key)
    try:
        cursor = conn.cursor(as_dict=True)
        
        sql = f"""
            SELECT TOP {limit}
                CAST(p.FullName AS NVARCHAR(200)) as name,
                SUM(ABS(t.Qty)) as value,
                SUM(ABS(t.Total)) as amount
            FROM DlySale t
            JOIN Dlyndx d ON t.VchCode = d.VchCode
            LEFT JOIN Ptype p ON t.PtypeId = p.TypeId
            WHERE d.Date BETWEEN '{start_date}' AND '{end_date}' 
              AND d.Draft = 2 
              AND d.VchType = 11
            GROUP BY p.FullName
            ORDER BY value DESC
        """
        cursor.execute(sql)
        rows = cursor.fetchall()
        return rows
    except Exception as e:
        logger.error(f"Error fetching SKU ranking: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn: conn.close()
