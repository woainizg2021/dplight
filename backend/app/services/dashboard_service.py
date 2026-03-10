from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
import asyncio
from concurrent.futures import ThreadPoolExecutor
from backend.app.db.mssql import get_db_connection
from backend.app.db.mysql import get_mysql_connection
from backend.app.core.cache import cache_service
from backend.app.core.config import settings
from backend.app.models.schemas import (
    DashboardResponse, CompanyDashboardData, SalesTrend, DashboardAlert
)
import logging

logger = logging.getLogger(__name__)

class DashboardService:
    
    # 公司名称映射
    COMPANY_NAMES = {
        "UGANDA": {"short_name": "乌干达", "full_name": "乌干达灯具制造"},
        "NIGERIA": {"short_name": "尼日利亚", "full_name": "尼日利亚灯具制造"},
        "KENYA": {"short_name": "肯尼亚", "full_name": "肯尼亚灯具制造"},
        "KENYA_AUDIO": {"short_name": "肯尼亚音箱", "full_name": "肯尼亚音箱制造"},
        "DRC": {"short_name": "刚果金", "full_name": "刚果金灯具制造"}
    }
    
    # 货币映射
    CURRENCY_MAP = {
        "UGANDA": "UGX",
        "NIGERIA": "NGN", 
        "KENYA": "KES",
        "KENYA_AUDIO": "KES",
        "DRC": "CDF"
    }
    
    def get_today_dashboard(self, query_date: Optional[date] = None) -> DashboardResponse:
        """获取今日快报数据"""
        if not query_date:
            query_date = date.today()
            
        date_str = query_date.strftime('%Y-%m-%d')
        cache_key = f"dashboard:today:{date_str}"
        
        # 尝试缓存
        cached = cache_service.get(cache_key)
        if cached:
            return DashboardResponse(**cached)
        
        # 并行获取所有公司数据
        companies = []
        sales_trend = self._get_sales_trend(query_date)
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_company = {
                executor.submit(self._get_company_dashboard_data, company, query_date): company
                for company in settings.COMPANY_DB_MAP.keys()
            }
            
            for future in future_to_company:
                company_key = future_to_company[future]
                try:
                    company_data = future.result()
                    companies.append(company_data)
                except Exception as e:
                    logger.error(f"获取 {company_key} 数据失败: {e}")
                    # 返回错误状态的数据
                    companies.append(self._get_error_company_data(company_key, date_str))
        
        # 按指定顺序排序
        order = ['UGANDA', 'NIGERIA', 'KENYA', 'KENYA_AUDIO', 'DRC']
        companies.sort(key=lambda x: order.index(x.key) if x.key in order else 99)
        
        result = DashboardResponse(
            updated_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            companies=companies,
            sales_trend=sales_trend
        )
        
        # 缓存结果
        cache_service.set(cache_key, result.model_dump(), settings.DASHBOARD_CACHE_TTL)
        
        return result
    
    def _get_company_dashboard_data(self, company_key: str, query_date: date) -> CompanyDashboardData:
        """获取单个公司仪表板数据"""
        date_str = query_date.strftime('%Y-%m-%d')
        start_month = query_date.strftime('%Y-%m-01')
        
        conn = None
        try:
            conn = get_db_connection(company_key)
            with conn.cursor(as_dict=True) as cursor:
                # 1. 今日销售额
                sql_sales_today = """
                    SELECT SUM(ABS(Total)) as total 
                    FROM Dlyndx 
                    WHERE VchType = 11 AND Date = %s AND Draft = 2
                """
                cursor.execute(sql_sales_today, (date_str,))
                row = cursor.fetchone()
                today_sales = float(row['total']) if row and row['total'] else 0.0
                
                # 2. 本月销售额
                sql_sales_month = """
                    SELECT SUM(ABS(Total)) as total 
                    FROM Dlyndx 
                    WHERE VchType = 11 AND Date BETWEEN %s AND %s AND Draft = 2
                """
                cursor.execute(sql_sales_month, (start_month, f"{date_str} 23:59:59"))
                row = cursor.fetchone()
                mtd_sales = float(row['total']) if row and row['total'] else 0.0
                
                # 3. 今日产量 (完工验收单 VchType=174)
                sql_prod_today = """
                    SELECT SUM(ABS(o.Qty)) as qty
                    FROM DlyOther o 
                    JOIN Dlyndx n ON o.VchCode = n.VchCode
                    WHERE n.VchType = 174 AND n.Date = %s AND n.Draft = 2
                """
                cursor.execute(sql_prod_today, (date_str,))
                row = cursor.fetchone()
                today_production = float(row['qty']) if row and row['qty'] else 0.0
                
                # 4. 银行余额
                sql_balance = """
                    SELECT SUM(Amt) as balance FROM (
                        SELECT SUM(ISNULL(DebitTotal,0) - ISNULL(CreditTotal,0)) as Amt FROM DlyBank
                        UNION ALL
                        SELECT SUM(ISNULL(DebitTotal,0) - ISNULL(CreditTotal,0)) as Amt FROM DlyCash
                    ) t
                """
                cursor.execute(sql_balance)
                row = cursor.fetchone()
                bank_balance = float(row['balance']) if row and row['balance'] else 0.0
                
                # 5. 预警检查
                alerts = self._check_alerts(company_key, cursor, query_date, today_sales, today_production, bank_balance)
                
                # 获取目标 (从MySQL预算表)
                mtd_target = self._get_monthly_target(company_key, query_date)
                
                company_info = self.COMPANY_NAMES.get(company_key, {"short_name": company_key, "full_name": company_key})
                
                return CompanyDashboardData(
                    key=company_key,
                    short_name=company_info["short_name"],
                    full_name=company_info["full_name"],
                    currency=self.CURRENCY_MAP.get(company_key, "USD"),
                    today_sales=today_sales,
                    mtd_sales=mtd_sales,
                    mtd_target=mtd_target,
                    today_production=today_production,
                    bank_balance=bank_balance,
                    alerts=alerts
                )
                
        except Exception as e:
            logger.error(f"获取 {company_key} 公司数据失败: {e}")
            raise e
        finally:
            if conn:
                conn.close()
    
    def _get_sales_trend(self, query_date: date) -> SalesTrend:
        """获取7天销售趋势"""
        end_date = query_date
        start_date = end_date - timedelta(days=6)
        
        dates = []
        uganda_data = []
        nigeria_data = []
        kenya_data = []
        kenya_audio_data = []
        drc_data = []
        
        current_date = start_date
        while current_date <= end_date:
            date_str = current_date.strftime('%Y-%m-%d')
            dates.append(date_str)
            
            # 并行获取每日销售数据
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = {
                    executor.submit(self._get_daily_sales, company, current_date): company
                    for company in settings.COMPANY_DB_MAP.keys()
                }
                
                daily_data = {}
                for future in futures:
                    company = futures[future]
                    try:
                        daily_data[company] = future.result()
                    except Exception as e:
                        logger.error(f"获取 {company} {date_str} 销售数据失败: {e}")
                        daily_data[company] = 0.0
            
            uganda_data.append(daily_data.get("UGANDA", 0.0))
            nigeria_data.append(daily_data.get("NIGERIA", 0.0))
            kenya_data.append(daily_data.get("KENYA", 0.0))
            kenya_audio_data.append(daily_data.get("KENYA_AUDIO", 0.0))
            drc_data.append(daily_data.get("DRC", 0.0))
            
            current_date += timedelta(days=1)
        
        return SalesTrend(
            dates=dates,
            UGANDA=uganda_data,
            NIGERIA=nigeria_data,
            KENYA=kenya_data,
            KENYA_AUDIO=kenya_audio_data,
            DRC=drc_data
        )
    
    def _get_daily_sales(self, company_key: str, query_date: date) -> float:
        """获取单日销售额"""
        date_str = query_date.strftime('%Y-%m-%d')
        
        conn = None
        try:
            conn = get_db_connection(company_key)
            with conn.cursor() as cursor:
                sql = """
                    SELECT SUM(ABS(Total)) as total 
                    FROM Dlyndx 
                    WHERE VchType = 11 AND Date = %s AND Draft = 2
                """
                cursor.execute(sql, (date_str,))
                row = cursor.fetchone()
                return float(row[0]) if row and row[0] else 0.0
        except Exception as e:
            logger.error(f"获取 {company_key} {date_str} 销售数据失败: {e}")
            return 0.0
        finally:
            if conn:
                conn.close()
    
    def _check_alerts(self, company_key: str, cursor, query_date: date, 
                     today_sales: float, today_production: float, bank_balance: float) -> List[DashboardAlert]:
        """检查预警信息"""
        alerts = []
        
        # 1. 当日无销售记录
        if today_sales <= 0:
            alerts.append(DashboardAlert(
                type="sales",
                msg="今日暂无销售"
            ))
        
        # 2. 无生产记录 (DRC除外)
        if today_production <= 0 and company_key != 'DRC':
            alerts.append(DashboardAlert(
                type="production",
                msg="今日无生产记录"
            ))
        
        # 3. 库存预警 - 热销32款库存检查
        stock_alerts = self._check_stock_alerts(company_key, cursor)
        alerts.extend(stock_alerts)
        
        # 4. 应收账款预警 - 超60天
        ar_alerts = self._check_ar_alerts(company_key, cursor)
        alerts.extend(ar_alerts)
        
        # 5. 银行余额预警 (从MySQL配置表读取预警线)
        cash_alerts = self._check_cash_alerts(company_key, bank_balance)
        alerts.extend(cash_alerts)
        
        return alerts
    
    def _check_stock_alerts(self, company_key: str, cursor) -> List[DashboardAlert]:
        """检查库存预警"""
        alerts = []
        
        # 热销32款ID列表
        hot_32_ids = [
            '000020000100002','000020000100003','000020000100006','000020000100007',
            '000020000300006','000020000400004','000020000400007','000020000400010',
            '000020000400012','000020000400018','000020000400024','000020000400025',
            '000020000500007','000020000500012','000020000500017','000020000500023',
            '000020000500024','000020000500025','000020000500026','000020000500027',
            '000020000500029','000020000500034','000020000500038','000020000500039',
            '000020000500044','000020000500045','000020000800001','000020000900037',
            '000020001200013','000020001200014','000020001200018','000020002700001'
        ]
        
        # 检查热销款库存 (假设安全库存为6箱)
        sql = """
            SELECT TOP 5
                CAST(p.FullName AS NVARCHAR(200)) as product_name,
                SUM(g.Qty) as stock_qty,
                ISNULL(p.UnitRate1, 1) as unit_rate
            FROM GoodsStocks g
            JOIN Ptype p ON g.PtypeId = p.TypeId
            WHERE g.PtypeId IN ({}) 
            AND g.KtypeId IN ('00003', '00011') -- 门市和成品仓库
            GROUP BY p.FullName, p.UnitRate1
            HAVING SUM(g.Qty) / ISNULL(p.UnitRate1, 1) < 6
            ORDER BY SUM(g.Qty) / ISNULL(p.UnitRate1, 1) ASC
        """.format(','.join([f"'{id}'" for id in hot_32_ids]))
        
        try:
            cursor.execute(sql)
            rows = cursor.fetchall()
            for row in rows:
                box_count = float(row['stock_qty']) / float(row['unit_rate']) if row['unit_rate'] > 0 else 0
                alerts.append(DashboardAlert(
                    type="stock",
                    msg=f"{row['product_name']}库存不足({box_count:.1f}箱)"
                ))
        except Exception as e:
            logger.warning(f"库存预警检查失败 {company_key}: {e}")
        
        return alerts
    
    def _check_ar_alerts(self, company_key: str, cursor) -> List[DashboardAlert]:
        """检查应收账款预警"""
        alerts = []
        
        # 检查超60天应收账款
        sql = """
            SELECT COUNT(*) as count
            FROM v_应收账龄分析
            WHERE [账龄天数] > 60 AND [应收余额] > 0
        """
        
        try:
            cursor.execute(sql)
            row = cursor.fetchone()
            count = int(row['count']) if row and row['count'] else 0
            if count > 0:
                alerts.append(DashboardAlert(
                    type="ar",
                    msg=f"有{count}笔应收逾期60天"
                ))
        except Exception as e:
            logger.warning(f"应收预警检查失败 {company_key}: {e}")
        
        return alerts
    
    def _check_cash_alerts(self, company_key: str, bank_balance: float) -> List[DashboardAlert]:
        """检查现金余额预警"""
        alerts = []
        
        try:
            # 从MySQL获取预警线配置
            conn_mysql = get_mysql_connection()
            with conn_mysql.cursor() as cursor:
                sql = """
                    SELECT warning_threshold 
                    FROM cash_warning_config 
                    WHERE company_key = %s AND is_active = 1
                    ORDER BY created_at DESC 
                    LIMIT 1
                """
                cursor.execute(sql, (company_key,))
                row = cursor.fetchone()
                
                if row and row['warning_threshold']:
                    threshold = float(row['warning_threshold'])
                    if bank_balance < threshold:
                        alerts.append(DashboardAlert(
                            type="cash",
                            msg=f"银行余额低于预警线({threshold:,.0f})"
                        ))
            
            conn_mysql.close()
        except Exception as e:
            logger.warning(f"现金预警检查失败 {company_key}: {e}")
        
        return alerts
    
    def _get_monthly_target(self, company_key: str, query_date: date) -> float:
        """获取月度销售目标"""
        try:
            conn_mysql = get_mysql_connection()
            with conn_mysql.cursor() as cursor:
                sql = """
                    SELECT target_amount
                    FROM sales_targets 
                    WHERE company_key = %s AND year = %s AND month = %s
                """
                cursor.execute(sql, (company_key, query_date.year, query_date.month))
                row = cursor.fetchone()
                
                return float(row['target_amount']) if row and row['target_amount'] else 0.0
            
            conn_mysql.close()
        except Exception as e:
            logger.warning(f"获取月度目标失败 {company_key}: {e}")
            return 0.0
    
    def _get_error_company_data(self, company_key: str, date_str: str) -> CompanyDashboardData:
        """返回错误状态的公司数据"""
        company_info = self.COMPANY_NAMES.get(company_key, {"short_name": company_key, "full_name": company_key})
        return CompanyDashboardData(
            key=company_key,
            short_name=company_info["short_name"],
            full_name=company_info["full_name"],
            currency=self.CURRENCY_MAP.get(company_key, "USD"),
            today_sales=0.0,
            mtd_sales=0.0,
            mtd_target=0.0,
            today_production=0.0,
            bank_balance=0.0,
            alerts=[DashboardAlert(type="error", msg="数据获取失败")]
        )

# 创建服务实例
dashboard_service = DashboardService()

# 便捷函数
def get_dashboard_service():
    return dashboard_service