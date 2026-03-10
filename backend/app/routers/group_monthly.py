from fastapi import APIRouter
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import datetime
import calendar
import pymssql
import logging
from backend.app.config import ERP_CREDENTIALS, ERP_HOST, ERP_PORT

router = APIRouter()
logger = logging.getLogger(__name__)

# Same as Group Daily
EXCHANGE_RATES = {
    'UGANDA': 3744,
    'NIGERIA': 1512,
    'KENYA': 129.6,
    'KENYA_AUDIO': 129.6,
    'DRC': 1
}

# Monthly Targets (USD) - Placeholder
TARGETS_USD = {
    'UGANDA': 1500000,
    'NIGERIA': 1000000,
    'KENYA': 500000,
    'KENYA_AUDIO': 200000,
    'DRC': 300000
}

FLAGS = {
    'UGANDA': '🇺🇬',
    'NIGERIA': '🇳🇬',
    'KENYA': '🇰🇪',
    'KENYA_AUDIO': '🔊',
    'DRC': '🇨🇩'
}

def fetch_tenant_monthly(tenant_key: str, creds: Dict[str, Any], month_str: str) -> Dict[str, Any]:
    """Fetch monthly data for a single tenant."""
    # Dates
    y, m = map(int, month_str.split('-'))
    start_date = f"{month_str}-01"
    end_day = calendar.monthrange(y, m)[1]
    end_date = f"{month_str}-{end_day} 23:59:59"
    
    # Last Month
    lm_date = datetime.date(y, m, 1) - datetime.timedelta(days=1)
    lm_str = lm_date.strftime('%Y-%m')
    lm_start = f"{lm_str}-01"
    lm_end = f"{lm_str}-{calendar.monthrange(lm_date.year, lm_date.month)[1]} 23:59:59"

    res = {
        'key': tenant_key,
        'name': creds.get('name', tenant_key),
        'currency': creds.get('currency', ''),
        'flag': FLAGS.get(tenant_key, ''),
        'rate': EXCHANGE_RATES.get(tenant_key, 1),
        'sales_current': 0.0,
        'sales_last_month': 0.0,
        'target_usd': TARGETS_USD.get(tenant_key, 0),
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
            # 1. Current Month Sales
            sql = f"SELECT SUM(Total) FROM Dlyndx WHERE VchType = 11 AND Draft = 2 AND Date BETWEEN '{start_date}' AND '{end_date}'"
            cursor.execute(sql)
            row = cursor.fetchone()
            if row and row[0]: res['sales_current'] = float(row[0])
            
            # 2. Last Month Sales
            sql_lm = f"SELECT SUM(Total) FROM Dlyndx WHERE VchType = 11 AND Draft = 2 AND Date BETWEEN '{lm_start}' AND '{lm_end}'"
            cursor.execute(sql_lm)
            row = cursor.fetchone()
            if row and row[0]: res['sales_last_month'] = float(row[0])
            
        conn.close()
    except Exception as e:
        logger.error(f"Error fetching monthly {tenant_key}: {e}")
        res['error'] = str(e)
        
    return res

@router.get("/summary", response_model=List[Dict[str, Any]])
async def get_group_monthly_summary(month: str = None):
    """
    Get aggregated monthly summary.
    """
    if not month:
        month = datetime.date.today().strftime('%Y-%m')
        
    results = []
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_tenant = {
            executor.submit(fetch_tenant_monthly, k, v, month): k 
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
