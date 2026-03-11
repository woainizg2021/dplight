from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import datetime
import pymssql
import logging
from app.config import ERP_CREDENTIALS, ERP_HOST, ERP_PORT
from app.models.schemas import DashboardData

router = APIRouter()
logger = logging.getLogger(__name__)

# Exchange Rates Configuration
EXCHANGE_RATES = {
    'UGANDA': 3744,
    'NIGERIA': 1512,
    'KENYA': 129.6,
    'KENYA_AUDIO': 129.6,
    'DRC': 1
}

FLAGS = {
    'UGANDA': '🇺🇬',
    'NIGERIA': '🇳🇬',
    'KENYA': '🇰🇪',
    'KENYA_AUDIO': '🔊',
    'DRC': '🇨🇩'
}

def fetch_tenant_data(tenant_key: str, creds: Dict[str, Any]) -> Dict[str, Any]:
    """Fetch daily data for a single tenant."""
    today = datetime.date.today().strftime('%Y-%m-%d')
    start_month = datetime.date.today().strftime('%Y-%m-01')
    
    res = {
        'key': tenant_key,
        'name': creds.get('name', tenant_key),
        'currency': creds.get('currency', ''),
        'flag': FLAGS.get(tenant_key, ''),
        'rate': EXCHANGE_RATES.get(tenant_key, 1),
        'sales_today': 0.0,
        'sales_month': 0.0,
        'prod_today': 0.0,
        'balance': 0.0,
        'has_production': False,
        'error': None
    }
    
    try:
        conn = pymssql.connect(
            server=ERP_HOST,
            port=ERP_PORT,
            user=creds['user'],
            password=creds['pass'],
            database=creds['db'],
            charset='utf8'
        )
        
        with conn.cursor() as cursor:
            # 1. Sales Today (VchType 11)
            cursor.execute(f"SELECT SUM(Total) FROM Dlyndx WHERE VchType = 11 AND Draft = 2 AND Date = '{today}'")
            row = cursor.fetchone()
            if row and row[0]: res['sales_today'] = float(row[0])
            
            # 2. Sales Month
            cursor.execute(f"SELECT SUM(Total) FROM Dlyndx WHERE VchType = 11 AND Draft = 2 AND Date BETWEEN '{start_month}' AND '{today} 23:59:59'")
            row = cursor.fetchone()
            if row and row[0]: res['sales_month'] = float(row[0])

            # 3. Production Today (VchType 174)
            sql_prod = f"""
                SELECT SUM(ABS(o.Qty)) 
                FROM DlyOther o JOIN Dlyndx n ON o.VchCode = n.VchCode
                WHERE n.VchType = 174 AND n.Draft = 2 AND n.Date = '{today}'
            """
            cursor.execute(sql_prod)
            row = cursor.fetchone()
            if row and row[0]: 
                res['prod_today'] = float(row[0])
                res['has_production'] = res['prod_today'] > 0

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
            if row and row[0]: res['balance'] = float(row[0])
            
        conn.close()
        
        # Add Warnings
        warnings = []
        if not res['has_production'] and tenant_key != 'DRC':
            warnings.append("停机预警")
        res['warnings'] = warnings
            
    except Exception as e:
        logger.error(f"Error fetching {tenant_key}: {e}")
        res['error'] = str(e)
        res['warnings'] = ["连接失败"]
        
    return res

@router.get("/summary", response_model=List[Dict[str, Any]])
async def get_group_daily_summary():
    """
    Get aggregated daily summary for all tenants.
    """
    results = []
    
    # Use ThreadPoolExecutor for parallel fetching
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_tenant = {
            executor.submit(fetch_tenant_data, k, v): k 
            for k, v in ERP_CREDENTIALS.items()
        }
        
        for future in as_completed(future_to_tenant):
            try:
                data = future.result()
                results.append(data)
            except Exception as exc:
                logger.error(f"Tenant execution error: {exc}")
                
    # Sort results
    order = ['UGANDA', 'NIGERIA', 'KENYA', 'KENYA_AUDIO', 'DRC']
    results.sort(key=lambda x: order.index(x['key']) if x['key'] in order else 99)
    
    return results
